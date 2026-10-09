"""ai-tools-doctor command line. Read-only: never installs, logs in, or edits configuration."""
from __future__ import annotations

import argparse
import getpass
import importlib.util
import json
import os
import sys
from pathlib import Path

from . import config, context, install, probe, proc, report, skills
from .model import result
from .redact import origin, tilde

CLIENT_CHOICES = ("codex", "claude", "opencode", "all")


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print("ai-tools-doctor: invalid arguments; run with --help for supported options.", file=sys.stderr)
        raise SystemExit(2)


class InvalidNativeNote(ValueError):
    pass


def parser() -> argparse.ArgumentParser:
    p = SafeArgumentParser(
        prog="ai-tools-doctor",
        description="Read-only health check. Default: inventory only (no live MCP connections). "
                    "Use `ai-tools-doctor setup` once to install the locked runtime.")
    p.add_argument("--project", help="inventory using this project's configuration context")
    p.add_argument("--probe", action="store_true", help="live bounded checks; needs --server")
    p.add_argument("--server", action="append", default=[], help="server name to probe (repeatable)")
    p.add_argument("--client", action="append", choices=CLIENT_CHOICES, default=[],
                   help="client to inspect/probe (repeatable; default all)")
    p.add_argument("--output-dir", help="report directory (default: timestamped under $XDG_STATE_HOME/ai-tools-doctor)")
    p.add_argument("--deadline", type=float, default=600, help="overall deadline in seconds (default 600)")
    p.add_argument("--kind", choices=("mac", "vm"), help="override detected machine kind (for fixtures)")
    p.add_argument("--role", choices=("personal", "work"), help="override detected role (for fixtures)")
    p.add_argument("--native-note", action="append", default=[], metavar="CLIENT/SERVER=OUTCOME:TEXT",
                   help="record a native-client call you made yourself, e.g. codex/codebase-memory-mcp=passed:list_projects ok")
    return p


def progress(message: str) -> None:
    print(f"[ai-tools-doctor] {message}", file=sys.stderr, flush=True)


def selected_clients(args) -> list[str]:
    chosen = args.client or ["all"]
    return list(context.CLIENTS) if "all" in chosen else [c for c in context.CLIENTS if c in chosen]


def runtime_available() -> bool:
    return importlib.util.find_spec("mcp") is not None


def parse_native_note(note: str) -> tuple[str, str, str]:
    target, sep, rest = note.partition("=")
    client, slash, server = target.partition("/")
    outcome, colon, _text = rest.partition(":")
    valid = (bool(sep) and bool(slash) and client in context.CLIENTS and bool(server.strip())
             and server.isprintable()
             and outcome in ("passed", "failed", "unverified", "auth_required"))
    if not valid:
        raise InvalidNativeNote
    return client, server, outcome


def native_notes(notes: list[tuple[str, str, str]]) -> list[dict]:
    rows = []
    for client, server, outcome in notes:
        rows.append(result(client=client, server=server, check="native-client call (user-recorded)", layer="native",
                           outcome=outcome, reason_code="user_recorded_result",
                           detail="User-recorded result.", provenance="--native-note", informational=True))
    return rows


def _run(args, notes: list[tuple[str, str, str]]) -> int:
    if args.probe and not args.server:
        print("--probe needs at least one --server NAME", file=sys.stderr)
        return report.EXIT_INCOMPLETE
    if args.server and not args.probe:
        print("--server only applies with --probe", file=sys.stderr)
        return report.EXIT_INCOMPLETE
    ctx = context.build(args.project, args.kind, args.role)
    clients = selected_clients(args)
    out_dir = Path(args.output_dir).expanduser() if args.output_dir else report.default_output_dir(ctx.env)
    started = os.times()
    rows: list[dict] = []
    servers: list = []
    tools: dict = {}
    skill_summary: dict = {}
    state = None
    doc_started = result(client="-", check="-", layer="installation", outcome="passed", detail="")["timestamp"]
    proc.install_cancellation(args.deadline)
    try:
        progress(f"inventory: installations ({', '.join(clients)})")
        r, tools = install.inventory(ctx, clients)
        rows += r
        progress("inventory: configuration")
        for client in clients:
            found, extra = config.READERS[client](ctx)
            servers += found
            rows += extra
        for cfg in servers:
            rows.append(result(client=cfg.client, server=cfg.name, check="declared", layer="configuration",
                               outcome="passed" if cfg.enabled else "skipped",
                               detail=("Configured" if cfg.enabled else "Configured but disabled")
                                      + f" ({cfg.transport}); inventory only, not connected.",
                               provenance=cfg.provenance, informational=True))
        progress("inventory: skills")
        r, skill_summary = skills.analyze(ctx)
        rows += r
        if args.probe:
            if not runtime_available():
                for name in args.server:
                    rows.append(result(client="all", server=name, check="probe runtime", layer="connection",
                                       outcome="unverified", requested=True,
                                       detail="The locked MCP SDK runtime is not installed; ordinary runs never install it.",
                                       next_action="Run: ai-tools-doctor setup"))
            else:
                explicit = bool(args.client) and "all" not in args.client
                for name in args.server:
                    nowhere = not any(s.name == name for s in servers)   # a typo must not exit 0
                    for client in clients:
                        cfg = next((s for s in servers if s.client == client and s.name == name), None)
                        if cfg is None:
                            rows.append(result(client=client, server=name, check="connection", layer="connection",
                                               outcome="skipped", requested=explicit or nowhere,
                                               detail=f"'{name}' is not configured in {client} for this context."))
                            continue
                        for row in probe.probe_server(ctx, cfg, out_dir, progress=progress):
                            row["requested"] = True
                            rows.append(row)
                        native = probe.native_status(ctx, cfg)
                        native["informational"] = True
                        rows.append(native)
        rows += native_notes(notes)
    except proc.Cancelled as exc:
        state = "deadline" if str(exc) == "deadline" else "cancelled"
        progress(f"{state}: stopping owned processes; writing partial report")
        proc.kill_owned()
    except Exception:
        state = "unexpected_failure"
        rows.append(result(client="-", check="doctor", layer="configuration", outcome="failed",
                           reason_code="unexpected_failure",
                           detail="Doctor failed unexpectedly; internal messages and tracebacks withheld."))
    finally:
        try:
            import signal
            signal.setitimer(signal.ITIMER_REAL, 0)
        except Exception:
            pass
    safe_servers = [s.safe(ctx.home, origin, tilde) for s in servers]
    rows = ctx.redactor.scrub_data(rows)
    code = report.exit_code(rows, state)
    doc = {
        "started": doc_started, "mode": "probe" if args.probe else "inventory", "state": state, "exit_code": code,
        "diagnostic_policy": "structured",
        "account": {"user": getpass.getuser(), "kind": ctx.kind, "role": ctx.role, "profile_source": ctx.profile_source},
        "project": tilde(ctx.project, ctx.home), "clients": clients, "tools": tools, "skills": skill_summary,
        "servers": safe_servers, "results": rows, "proof": report.proof_levels(safe_servers, rows),
        "sanitizer": {"limitations": report.SANITIZER_LIMITATIONS},
    }
    doc = ctx.redactor.scrub_data(doc)
    try:
        json_text, md_text = report.write(out_dir, doc, ctx.scrub, ctx.redactor.leaks)
    except PermissionError:   # gate trips before anything is written
        print("Refusing to publish: diagnostic safety check failed.", file=sys.stderr)
        return report.EXIT_INCOMPLETE
    print(md_text)
    print(f"Report: {tilde(str(out_dir), ctx.home)}  (result.json, summary.md)", file=sys.stderr)
    return code


def main(argv: list[str] | None = None) -> int:
    os.umask(0o077)
    args = parser().parse_args(argv)
    try:
        notes = [parse_native_note(note) for note in args.native_note]
    except InvalidNativeNote:
        print("ai-tools-doctor: invalid arguments; run with --help for supported options.", file=sys.stderr)
        return report.EXIT_INCOMPLETE
    try:
        return _run(args, notes)
    except Exception:
        failure = result(client="-", check="doctor", layer="configuration", outcome="failed",
                         reason_code="unexpected_failure",
                         detail="Doctor failed unexpectedly; internal messages and tracebacks withheld.")
        structured = {"diagnostic_policy": "structured", "state": "unexpected_failure",
                      "exit_code": report.EXIT_FAILED, "results": [failure]}
        print(json.dumps(structured, sort_keys=True), file=sys.stderr)
        return report.EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
