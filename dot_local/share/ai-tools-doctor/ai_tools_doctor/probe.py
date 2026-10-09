"""Bounded probes that publish structured summaries without retaining tool output."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from . import proc, smoke
from .context import Context
from .model import OUTCOMES, ServerConfig, result

BACKSTOP_SECONDS = 20 + 10 + 5
SETUP_HINT = ("Package-manager launcher would download and run code. Install the server first (owning source: "
              "dotfiles run-script that registers it, or the project) and register the installed binary.")
WORKER_ENV_KEYS = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "XDG_STATE_HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME")
EVENT_STAGES = {"connection", "discovery", "smoke"}
EVENT_REASONS = {
    "initialize_succeeded", "tools_discovered", "smoke_passed", "smoke_not_available", "smoke_tool_unavailable",
    "zero_tools", "pagination_limit", "timeout", "executable_not_found", "permission_denied", "http_error",
    "http_401", "http_403", "protocol_error", "connection_error", "smoke_tool_error", "smoke_response_invalid",
    "unexpected_failure",
}


def _row(cfg: ServerConfig, **kw):
    return result(client=cfg.client, server=cfg.name, provenance=cfg.provenance, **kw)


def precheck(ctx: Context, cfg: ServerConfig) -> dict | None:
    """Return a skip/unverified row when a direct SDK probe is not safe or possible."""
    if not cfg.enabled:
        return _row(cfg, check="connection", layer="connection", outcome="skipped",
                    reason_code="disabled", detail="Server is disabled; not started.",
                    next_action="Enable it in the client if needed.")
    if cfg.approval == "pending approval":
        return _row(cfg, check="connection", layer="connection", outcome="skipped",
                    reason_code="approval_pending",
                    detail="Project server awaits Claude approval; the doctor never changes approvals.",
                    next_action="Approve or reject it interactively in Claude Code.")
    if cfg.approval == "rejected":
        return _row(cfg, check="connection", layer="connection", outcome="skipped", reason_code="approval_rejected",
                    detail="Project server was rejected by the user.")
    if cfg.launcher:
        return _row(cfg, check="connection", layer="connection", outcome="skipped", reason_code="package_launcher",
                    detail=f"Launcher '{os.path.basename(cfg.command)}' would fetch packages. {SETUP_HINT}",
                    next_action="Register an installed binary (see docs/plans/ai-tooling-followups.md).")
    if cfg.transport not in ("stdio", "http"):
        return _row(cfg, check="connection", layer="connection", outcome="unverified",
                    reason_code="unsupported_transport",
                    detail="Configured transport is unsupported by the direct probe.",
                    next_action="Check the server through its native client.")
    if cfg.unresolved:
        names = ", ".join(sorted(set(cfg.unresolved)))
        return _row(cfg, check="connection", layer="connection", outcome="unverified",
                    reason_code="unresolved_configuration",
                    detail=f"Configuration references {len(set(cfg.unresolved))} unresolved value(s): {names}.",
                    next_action="Provide the required variables in the doctor's environment, or use native status.")
    if cfg.transport == "http" and ("OAuth" in (cfg.auth or "") or cfg.auth == "o_auth") and not cfg.headers:
        return _row(cfg, check="connection", layer="connection", outcome="unverified",
                    reason_code="client_owned_oauth",
                    detail="Client-owned OAuth server; the doctor extracts no OAuth cache and runs no login.",
                    next_action="Use the client's native status interface.")
    if smoke.kind_for(cfg.name, cfg.command, cfg.args) == "github" and cfg.transport == "stdio":
        merged = dict(cfg.env) | {k: ctx.env[k] for k in cfg.forwarded_env if ctx.env.get(k)}
        if not any(merged.get(k) for k in ("GITHUB_PERSONAL_ACCESS_TOKEN", "GITHUB_TOKEN")):
            return _row(cfg, check="connection", layer="connection", outcome="unverified",
                        reason_code="credential_missing",
                        detail="GitHub server has no configured token; it could open a browser login.",
                        next_action="Provide the token through the owning registration; the doctor never logs in.")
    if cfg.transport == "stdio" and not cfg.command:
        return _row(cfg, check="connection", layer="connection", outcome="failed", reason_code="missing_command",
                    detail="Stdio server has no command.", next_action="Repair the registration.")
    if cfg.transport == "stdio" and cfg.cwd and not os.path.isabs(cfg.cwd):
        return _row(cfg, check="connection", layer="connection", outcome="unverified",
                    reason_code="relative_working_directory",
                    detail="Relative server working directory cannot be reconstructed outside its client.")
    return None


def request_for(ctx: Context, cfg: ServerConfig, want_smoke: bool) -> dict:
    env = dict(cfg.env)
    for name in cfg.forwarded_env:
        if name in ctx.env:
            env[name] = ctx.env[name]
    return {"transport": cfg.transport, "server": cfg.name, "command": cfg.command, "args": cfg.args,
            "env": env, "cwd": cfg.cwd, "url": cfg.url, "headers": cfg.headers, "smoke": want_smoke,
            "restrictions": cfg.tool_restrictions}


def _integer(event: dict, key: str, minimum: int = 0, maximum: int = 2**31 - 1) -> int | None:
    value = event.get(key)
    return value if type(value) is int and minimum <= value <= maximum else None


def _safe_event(event: object) -> dict | None:
    """Copy only known event fields and replace unknown failures with a closed reason code."""
    if not isinstance(event, dict) or event.get("stage") not in EVENT_STAGES:
        return None
    stage = event["stage"]
    outcome = event.get("outcome")
    if outcome not in OUTCOMES:
        outcome = "failed"
        reason = "unexpected_failure"
    else:
        reason = event.get("reason_code")
        if not isinstance(reason, str) or reason not in EVENT_REASONS:
            reason = "unexpected_failure" if outcome in ("failed", "timeout", "auth_required", "unverified") else None
        expected_success = {"connection": "initialize_succeeded", "discovery": "tools_discovered",
                            "smoke": "smoke_passed"}.get(stage)
        if outcome == "passed" and reason != expected_success:
            outcome, reason = "failed", "unexpected_failure"
        if reason in ("http_401", "http_403") and event.get("http_status") != int(reason[-3:]):
            outcome, reason = "failed", "unexpected_failure"
        if reason == "http_error" and _integer(event, "http_status", 100, 599) is None:
            outcome, reason = "failed", "unexpected_failure"
    safe = {"stage": stage, "outcome": outcome}
    if reason:
        safe["reason_code"] = reason
    for key, minimum, maximum in (("elapsed_ms", 0, 24 * 60 * 60 * 1000),
                                  ("http_status", 100, 599), ("protocol_code", -32768, 65535),
                                  ("exit_code", -255, 255), ("tools_count", 0, 1_000_000),
                                  ("pages_count", 0, 100_000)):
        value = _integer(event, key, minimum, maximum)
        if value is not None:
            safe[key] = value
    return safe


def _detail(event: dict) -> str:
    stage, outcome = event["stage"], event["outcome"]
    reason = event.get("reason_code", "unexpected_failure")
    elapsed = event.get("elapsed_ms")
    if outcome == "passed":
        if stage == "connection":
            return "MCP connection initialized."
        if stage == "discovery":
            return f"{event.get('tools_count', 0)} tools found across {event.get('pages_count', 0)} page(s)."
        return "Reviewed smoke call passed; response body withheld."
    if reason in ("http_401", "http_403"):
        return f"Authentication required (HTTP {event['http_status']})."
    if reason == "http_error":
        return f"Server returned HTTP {event.get('http_status', 'error')}."
    if reason == "executable_not_found":
        return "Server command was not found."
    if reason == "permission_denied":
        return "Server command could not be executed because permission was denied."
    if reason == "protocol_error":
        code = event.get("protocol_code")
        return f"MCP protocol error (code {code})." if code is not None else "MCP protocol error."
    if reason == "connection_error":
        return "Server connection failed."
    if reason == "pagination_limit":
        return f"Tool discovery exceeded the {event.get('pages_count', 0)} page limit."
    if reason == "zero_tools":
        return "Server connected but advertised no tools."
    if reason == "smoke_tool_unavailable":
        return "No reviewed smoke tool was available."
    if reason == "smoke_tool_error":
        return "Reviewed smoke call returned an error; response body withheld."
    if reason == "smoke_response_invalid":
        return "Reviewed smoke call returned an unexpected response; response body withheld."
    if reason == "smoke_not_available":
        return "No reviewed smoke call is defined for this server."
    if reason == "timeout":
        budget = f" after {elapsed} ms" if elapsed is not None else ""
        return f"{stage.capitalize()} stage timed out{budget}."
    if reason == "unexpected_failure":
        return f"Unexpected {stage} failure; provider messages and tracebacks withheld."
    return f"{stage.capitalize()} stage failed."


def _write_diagnostics(diag_dir: Path, stem: str, out: proc.Outcome, events: dict[str, dict]) -> str:
    diag_path = diag_dir / f"{stem}.json"
    diag = {
        "diagnostic_policy": "structured",
        "worker_stderr": "[withheld]",
        "server_stderr": "[withheld]",
        "worker_exit_code": out.returncode if type(out.returncode) is int else None,
        "worker_timed_out": bool(out.timed_out),
        "worker_elapsed_ms": out.elapsed_ms,
        "stages": [events[key] for key in ("connection", "discovery", "smoke") if key in events],
    }
    diag_path.write_text(json.dumps(diag, indent=2))
    diag_path.chmod(0o600)
    return f"diagnostics/{diag_path.name}"


def probe_server(ctx: Context, cfg: ServerConfig, out_dir: Path, python: str | None = None,
                 progress=lambda msg: None) -> list[dict]:
    skip = precheck(ctx, cfg)
    if skip:
        return [skip]
    diag_dir = out_dir / "diagnostics"
    diag_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stem = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{cfg.client}-{cfg.name}")
    request = request_for(ctx, cfg, want_smoke=True)
    worker_env = {k: ctx.env[k] for k in WORKER_ENV_KEYS if k in ctx.env}
    package_root = str(Path(__file__).resolve().parent.parent)
    worker_env["PYTHONPATH"] = package_root
    worker_env["PYTHONDONTWRITEBYTECODE"] = "1"
    progress(f"probing {cfg.client}/{cfg.name} ({cfg.transport})")
    out = proc.run([python or sys.executable, "-m", "ai_tools_doctor.worker"],
                   timeout=BACKSTOP_SECONDS, env=worker_env, cwd=package_root, stdin=json.dumps(request))
    events: dict[str, dict] = {}
    done_seen = False
    for line in out.lines:
        try:
            raw_event = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(raw_event, dict) and raw_event.get("stage") == "done":
            done_seen = raw_event.get("outcome") == "passed" and raw_event.get("reason_code") == "worker_finished"
            continue
        event = _safe_event(raw_event)
        if event:
            events[event["stage"]] = event
    diagnostics = _write_diagnostics(diag_dir, stem, out, events)
    rows = []
    missing = sorted(n for n in cfg.forwarded_env if n not in ctx.env)

    def add(layer, check, event, default_next=""):
        outcome, reason_code = event["outcome"], event.get("reason_code", "")
        details = {"reason_code": reason_code, "detail": _detail(event), "diagnostics": diagnostics,
                   "elapsed_ms": event.get("elapsed_ms", out.elapsed_ms)}
        for key in ("http_status", "protocol_code", "exit_code", "tools_count", "pages_count"):
            if key in event:
                details[key] = event[key]
        if outcome == "auth_required":
            next_action = "Authenticate in the client itself; the doctor never logs in."
        elif outcome == "passed":
            next_action = ""
        else:
            next_action = default_next
        rows.append(_row(cfg, check=check, layer=layer, outcome=outcome,
                         detail=details.pop("detail"), next_action=next_action, **details))

    if out.spawn_error:
        rows.append(_row(cfg, check="connection", layer="connection", outcome="failed",
                         reason_code="worker_start_failed", detail="Probe worker could not be started.",
                         next_action="Run: ai-tools-doctor setup", diagnostics=diagnostics,
                         elapsed_ms=out.elapsed_ms))
        return rows
    for stage, layer, check, next_action in (
            ("connection", "connection", "initialize", "Repair the server registration or its binary."),
            ("discovery", "tools", "tools/list", "Check the server version and tools/list support."),
            ("smoke", "smoke", "smoke call", "Review the smoke result and confirm the server variant is supported.")):
        event = events.get(stage)
        if event:
            add(layer, check, event, next_action)
            if event["outcome"] not in ("passed", "skipped") and stage != "smoke":
                break
    if out.timed_out and not any(row["outcome"] == "timeout" for row in rows):
        rows.append(_row(cfg, check="worker backstop", layer="connection", outcome="timeout",
                         reason_code="worker_timeout",
                         detail=f"Probe exceeded its {BACKSTOP_SECONDS}s backstop; owned process tree was stopped.",
                         next_action="Inspect the server startup.", diagnostics=diagnostics, elapsed_ms=out.elapsed_ms))
    elif not done_seen and not any(
            row["outcome"] in ("failed", "timeout", "auth_required") for row in rows):
        rows.append(_row(cfg, check="connection", layer="connection", outcome="failed",
                         reason_code="worker_exit_without_result",
                         detail=f"Probe worker exited with code {out.returncode} without a result.",
                         next_action="Run: ai-tools-doctor setup", diagnostics=diagnostics,
                         exit_code=out.returncode, elapsed_ms=out.elapsed_ms))
    if missing and rows:
        rows[0]["detail"] += (f" Note: {len(missing)} forwarded variable(s) are unset in the doctor's environment "
                               f"({', '.join(missing[:6])}); the real client may differ.")
    return rows


def native_status(ctx: Context, cfg: ServerConfig) -> dict:
    """Separate native-client observation. Only per-server commands are used."""
    base = dict(client=cfg.client, server=cfg.name, layer="native", provenance=cfg.provenance)
    if cfg.client == "claude":
        refused = precheck(ctx, cfg)   # same gate as the direct probe: never start what we refused to start
        if refused and refused["outcome"] in ("skipped", "unverified"):
            return result(check="claude mcp get", outcome="skipped",
                          reason_code=refused.get("reason_code", "probe_refused"),
                          detail="Native status skipped because it could start a server the probe refused.",
                          next_action=refused.get("next_action", ""), **base)
        if not cfg.enabled or cfg.launcher or cfg.approval in ("pending approval", "rejected"):
            return result(check="claude mcp get", outcome="skipped", reason_code="server_not_safe_to_start",
                          detail="Native status would start a package-manager or unapproved server."
                          if cfg.launcher else "Server disabled or not approved; native status skipped.",
                          next_action=SETUP_HINT if cfg.launcher else "", **base)
        out = proc.run(["claude", "mcp", "get", cfg.name], timeout=15, env=ctx.env, cwd=ctx.project)
        match = re.search(r"Status:\s*([^\r\n]+)", out.stdout, re.IGNORECASE)
        status = match.group(1).strip().lower() if match else ""
        common = {**base, "elapsed_ms": out.elapsed_ms}
        if out.timed_out:
            return result(check="claude mcp get", outcome="timeout", reason_code="timeout",
                          detail="Native status exceeded its 15 s time limit.", **common)
        if re.match(r"^connected(?:\s|$)", status):
            return result(check="claude mcp get", outcome="passed", detail="Claude reports a connected status.", **common)
        if "auth" in status and "fail" not in status:
            numeric = {"exit_code": out.returncode} if type(out.returncode) is int else {}
            return result(check="claude mcp get", outcome="auth_required", reason_code="authentication_required",
                          detail="Claude reports that authentication is required.",
                          next_action="Authenticate inside Claude Code.", **{**common, **numeric})
        if status:
            numeric = {"exit_code": out.returncode} if type(out.returncode) is int else {}
            return result(check="claude mcp get", outcome="failed", reason_code="native_status_failed",
                          detail="Claude reports a failed server status.",
                          next_action="Review the server registration and retry native status.",
                          **{**common, **numeric})
        return result(check="claude mcp get", outcome="unverified", reason_code="native_status_unavailable",
                      detail="Claude did not return a recognized status.",
                      **{**common, **({"exit_code": out.returncode} if type(out.returncode) is int else {})})
    if cfg.client == "opencode":
        return result(check="opencode mcp list", outcome="unverified", reason_code="status_would_start_servers",
                      detail="OpenCode status checks every server, including package launchers; the doctor did not run it.",
                      next_action="Use opencode mcp list only when starting every configured server is acceptable.", **base)
    return result(check="codex mcp list", outcome="unverified", reason_code="status_is_configuration_only",
                  detail="Codex MCP inventory reports configuration and auth metadata, not connectivity.",
                  next_action="Call the tool from a Codex session and record only its structured outcome with --native-note.",
                  **base)
