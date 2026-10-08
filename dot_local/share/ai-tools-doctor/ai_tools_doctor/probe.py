"""Bounded live probes: SDK worker per target, plus separate native-client observation."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from . import proc, smoke
from .context import Context
from .model import ServerConfig, result

BACKSTOP_SECONDS = 20 + 10 + 5
SETUP_HINT = ("Package-manager launcher would download and run code. Install the server first (owning source: "
              "dotfiles run-script that registers it, or the project) and register the installed binary.")
WORKER_ENV_KEYS = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "XDG_STATE_HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME")


def _row(cfg: ServerConfig, **kw):
    return result(client=cfg.client, server=cfg.name, provenance=cfg.provenance, **kw)


def precheck(ctx: Context, cfg: ServerConfig) -> dict | None:
    """Return a skip/unverified row when a direct SDK probe is not safe or possible."""
    if not cfg.enabled:
        why = "; ".join(cfg.notes) or "disabled in client configuration"
        return _row(cfg, check="connection", layer="connection", outcome="skipped",
                    detail=f"Server is disabled ({why}); not started.", next_action="Enable it in the client if needed.")
    if cfg.approval == "pending approval":
        return _row(cfg, check="connection", layer="connection", outcome="skipped",
                    detail="Project .mcp.json server awaits Claude approval; the doctor never changes approvals.",
                    next_action="Approve or reject it interactively in Claude Code.")
    if cfg.approval == "rejected":
        return _row(cfg, check="connection", layer="connection", outcome="skipped",
                    detail="Project server was rejected by the user.")
    if cfg.launcher:
        return _row(cfg, check="connection", layer="connection", outcome="skipped",
                    detail=f"Launcher '{os.path.basename(cfg.command)}' would fetch packages. {SETUP_HINT}",
                    next_action="Register an installed binary (see docs/plans/ai-tooling-followups.md).")
    if cfg.transport not in ("stdio", "http"):
        return _row(cfg, check="connection", layer="connection", outcome="unverified",
                    detail=f"Transport '{cfg.transport}' is unsupported by the direct probe.",
                    next_action="Check the server through its native client.")
    if cfg.unresolved:
        return _row(cfg, check="connection", layer="connection", outcome="unverified",
                    detail="Configuration references values that cannot be reconstructed from the existing "
                           f"environment: {', '.join(sorted(set(cfg.unresolved)))}.",
                    next_action="Export those variables in the shell that runs the doctor, or use native status.")
    if cfg.transport == "http" and ("OAuth" in (cfg.auth or "") or cfg.auth == "o_auth") and not cfg.headers:
        return _row(cfg, check="connection", layer="connection", outcome="unverified",
                    detail="Client-owned OAuth server; the doctor extracts no OAuth cache and runs no login.",
                    next_action="Use the client's native status (claude mcp get / opencode mcp list).")
    if smoke.kind_for(cfg.name, cfg.command, cfg.args) == "github" and cfg.transport == "stdio":
        merged = dict(cfg.env) | {k: ctx.env[k] for k in cfg.forwarded_env if ctx.env.get(k)}
        if not any(merged.get(k) for k in ("GITHUB_PERSONAL_ACCESS_TOKEN", "GITHUB_TOKEN")):
            return _row(cfg, check="connection", layer="connection", outcome="unverified",
                        detail="GitHub server has no token in its configuration; it would open a browser login.",
                        next_action="Provide the token through the owning registration (mcp-github-register).")
    if cfg.transport == "stdio" and not cfg.command:
        return _row(cfg, check="connection", layer="connection", outcome="failed",
                    detail="Stdio server has no command.", next_action="Repair the registration.")
    if cfg.transport == "stdio" and cfg.cwd and not os.path.isabs(cfg.cwd):
        return _row(cfg, check="connection", layer="connection", outcome="unverified",
                    detail="Relative server working directory cannot be reconstructed outside its client.")
    return None


def request_for(ctx: Context, cfg: ServerConfig, stderr_path: str, want_smoke: bool) -> dict:
    env = dict(cfg.env)
    for name in cfg.forwarded_env:
        if name in ctx.env:
            env[name] = ctx.env[name]
    return {"transport": cfg.transport, "server": cfg.name, "command": cfg.command, "args": cfg.args,
            "env": env, "cwd": cfg.cwd, "url": cfg.url, "headers": cfg.headers, "smoke": want_smoke,
            "restrictions": cfg.tool_restrictions, "stderr_path": stderr_path}


def probe_server(ctx: Context, cfg: ServerConfig, out_dir: Path, python: str | None = None,
                 progress=lambda msg: None) -> list[dict]:
    skip = precheck(ctx, cfg)
    if skip:
        return [skip]
    diag_dir = out_dir / "diagnostics"
    diag_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stem = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{cfg.client}-{cfg.name}")
    stderr_path = str(diag_dir / f"{stem}.server-stderr.log")
    Path(stderr_path).unlink(missing_ok=True)   # never write through a pre-planted symlink
    request = request_for(ctx, cfg, stderr_path, want_smoke=True)
    worker_env = {k: ctx.env[k] for k in WORKER_ENV_KEYS if k in ctx.env}
    package_root = str(Path(__file__).resolve().parent.parent)
    worker_env["PYTHONPATH"] = package_root
    worker_env["PYTHONDONTWRITEBYTECODE"] = "1"
    progress(f"probing {cfg.client}/{cfg.name} ({cfg.transport})")
    out = proc.run([python or sys.executable, "-m", "ai_tools_doctor.worker"],
                   timeout=BACKSTOP_SECONDS, env=worker_env, cwd=package_root, stdin=json.dumps(request))
    stages = {}
    for line in out.lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        stages[event.get("stage")] = event
    server_err = ""
    try:
        server_err = Path(stderr_path).read_text(errors="replace")
    except OSError:
        pass
    # Scrub complete text first, then truncate, so a cut can never leave half a secret behind.
    diag = ctx.redactor.scrub_data({"worker_stderr": out.stderr, "server_stderr": server_err,
                                    "spawn_error": out.spawn_error, "returncode": out.returncode,
                                    "timed_out": out.timed_out, "stages": stages})
    for key in ("worker_stderr", "server_stderr"):
        diag[key] = diag[key][-4000:]
    diag_path = diag_dir / f"{stem}.json"
    diag_text = json.dumps(diag, indent=2)
    if ctx.redactor.leaks(diag_text):
        diag_text = json.dumps({"withheld": "sanitizer could not remove a registered secret from this diagnostic"})
    diag_path.write_text(diag_text)
    diag_path.chmod(0o600)
    try:
        os.unlink(stderr_path)  # raw server stderr is replaced by the scrubbed copy above
    except OSError:
        pass
    rel = f"diagnostics/{diag_path.name}"
    rows = []
    missing = sorted(n for n in cfg.forwarded_env if n not in ctx.env)
    def add(layer, check, event, default_next=""):
        rows.append(_row(cfg, check=check, layer=layer, outcome=event["outcome"],
                         detail=" ".join(ctx.scrub(event["detail"]).split())[:600],
                         next_action=("Authenticate in the client itself (Claude: /mcp, OpenCode: opencode mcp auth); "
                                      "the doctor never logs in." if event["outcome"] == "auth_required"
                                      else default_next if event["outcome"] != "passed" else ""),
                         diagnostics=rel, **({"server_info": " ".join(ctx.scrub(event["server_info"]).split())[:120]}
                                             if event.get("server_info") else {})))
    def finish(rows):
        if missing and rows:
            rows[0]["detail"] += (f" Note: {len(missing)} forwarded variable(s) unset in the doctor's environment "
                                  f"({', '.join(missing[:6])}); the real client may differ.")
        return rows
    if out.spawn_error:
        rows.append(_row(cfg, check="connection", layer="connection", outcome="failed",
                         detail=f"Worker could not start: {ctx.scrub(out.spawn_error)}",
                         next_action="Run: ai-tools-doctor setup", diagnostics=rel))
        return rows
    for layer, check in (("connection", "initialize"), ("discovery", "tools/list"), ("smoke", "smoke call")):
        event = stages.get(layer)
        if event:
            add("tools" if layer == "discovery" else layer, check, event,
                {"connection": "Repair the server registration or its binary; see diagnostics.",
                 "discovery": "Check the server version and tools/list support.",
                 "smoke": "Review the smoke diagnostic; confirm the server variant is supported."}[layer])
            if event["outcome"] not in ("passed", "skipped") and layer != "smoke":
                break
    if out.timed_out and not any(r["outcome"] == "timeout" for r in rows):
        rows.append(_row(cfg, check="worker backstop", layer="connection", outcome="timeout",
                         detail=f"Probe exceeded the {BACKSTOP_SECONDS}s backstop; owned process tree was stopped.",
                         next_action="Inspect the server's startup; see diagnostics.", diagnostics=rel))
    elif "done" not in stages and not any(r["outcome"] in ("failed", "timeout", "auth_required") for r in rows):
        rows.append(_row(cfg, check="connection", layer="connection", outcome="failed",
                         detail=f"Worker exited {out.returncode} without a result.",
                         next_action="See diagnostics.", diagnostics=rel))
    return finish(rows)


def native_status(ctx: Context, cfg: ServerConfig) -> dict:
    """Separate native-client observation. Only per-server commands are used."""
    base = dict(client=cfg.client, server=cfg.name, layer="native", provenance=cfg.provenance)
    if cfg.client == "claude":
        refused = precheck(ctx, cfg)   # same gate as the direct probe: never start what we refused to start
        if refused and refused["outcome"] in ("skipped", "unverified"):
            return result(check="claude mcp get", outcome="skipped",
                          detail="Native status skipped because `claude mcp get` would start this server: "
                                 + refused["detail"], next_action=refused.get("next_action", ""), **base)
        if not cfg.enabled or cfg.launcher or cfg.approval in ("pending approval", "rejected"):
            return result(check="claude mcp get", outcome="skipped",
                          detail="Native status would launch a package-manager server or an unapproved server."
                          if cfg.launcher else "Server disabled or not approved; native status skipped.",
                          next_action=SETUP_HINT if cfg.launcher else "", **base)
        out = proc.run(["claude", "mcp", "get", cfg.name], timeout=15, env=ctx.env, cwd=ctx.project)
        text = ctx.scrub(out.stdout)
        match = re.search(r"Status:\s*(.+)", text)
        status = match.group(1).strip() if match else ""
        if out.timed_out:
            return result(check="claude mcp get", outcome="timeout", detail="claude mcp get exceeded 15s.", **base)
        if "Connected" in status:
            return result(check="claude mcp get", outcome="passed", detail=f"Claude reports: {status}", **base)
        if "auth" in status.lower() and "fail" not in status.lower():
            return result(check="claude mcp get", outcome="auth_required", detail=f"Claude reports: {status}",
                          next_action="Authenticate inside Claude Code (/mcp).", **base)
        if status:
            return result(check="claude mcp get", outcome="failed", detail=f"Claude reports: {status}",
                          next_action="Run `claude mcp get " + cfg.name + "` and repair the registration.", **base)
        return result(check="claude mcp get", outcome="unverified",
                      detail=f"No status line in output (exit {out.returncode}).", **base)
    if cfg.client == "opencode":
        return result(check="opencode mcp list", outcome="unverified",
                      detail="OpenCode exposes connection status only through `opencode mcp list`, which health-checks "
                             "every server including package launchers; not run by the doctor.",
                      next_action="Run `opencode mcp list` yourself when launching all servers is acceptable.", **base)
    return result(check="codex mcp list", outcome="unverified",
                  detail="Codex `mcp list --json` reports configuration and auth metadata only, not connectivity. "
                         "Native proof needs a call through a Codex session.",
                  next_action="Call the server's tool from a Codex session and record it with --native-note.", **base)
