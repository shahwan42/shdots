"""Result aggregation, proof ladder, exit codes and private report files."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .model import PROOF_ORDER, now

EXIT_OK, EXIT_FAILED, EXIT_INCOMPLETE, EXIT_DEADLINE, EXIT_CANCELLED = 0, 1, 2, 124, 130
INCOMPLETE = {"unverified", "auth_required", "timeout"}
SANITIZER_LIMITATIONS = (
    "Redaction masks registered configuration secrets (env, headers, URL credentials, credential-bearing "
    "arguments), known token shapes (GitHub, OpenAI-style, Slack, AWS, JWT, Bearer) and database URIs. "
    "Secrets shorter than 6 characters, benign-looking values (true, info, http...) and unrecognised formats "
    "that appear only in third-party output could survive; diagnostics are "
    "scrubbed first and then capped at 4000 characters per stream and successful tool-response bodies are never stored.")


def exit_code(rows: list[dict], state: str | None) -> int:
    if state == "cancelled":
        return EXIT_CANCELLED
    if state == "deadline":
        return EXIT_DEADLINE
    if any(r["outcome"] == "failed" for r in rows if not r.get("informational")):
        return EXIT_FAILED
    for r in rows:
        if r.get("informational"):
            continue
        if r["outcome"] in INCOMPLETE:
            return EXIT_INCOMPLETE
        if r["outcome"] == "skipped" and r.get("requested") and r["layer"] != "smoke":
            return EXIT_INCOMPLETE
    return EXIT_OK


def proof_levels(servers: list[dict], rows: list[dict]) -> list[dict]:
    """Strongest established proof per client/server. Native-client proof is recorded separately."""
    ladder = []
    for server in servers:
        name, client = server["server"], server["client"]
        mine = [r for r in rows if r.get("server") == name and r["client"] == client]
        level = "configured" if server.get("enabled") else "none"
        if level == "configured" and client in ("codex", "opencode"):
            level = "discoverable"   # the client's own resolved export lists it
        native = next((r for r in mine if r["layer"] == "native"), None)
        if native and native["outcome"] in ("passed", "failed", "auth_required") and level == "configured":
            level = "discoverable"   # Claude recognised the server when asked directly
        for layer, rank in (("connection", "connected"), ("smoke", "smoke_passed")):
            if any(r["layer"] == layer and r["outcome"] == "passed" for r in mine):
                level = rank
        ladder.append({"client": client, "server": name, "proof": level,
                       "native_client": (native["outcome"] if native else "not_run")})
    ladder.sort(key=lambda e: (e["client"], e["server"]))
    assert all(e["proof"] in PROOF_ORDER for e in ladder)
    return ladder


def markdown(doc: dict) -> str:
    lines = [f"# AI tools doctor — {doc['started']}", "",
             f"Mode: **{doc['mode']}** · account `{doc['account']['user']}` · kind `{doc['account']['kind']}` · "
             f"role `{doc['account']['role']}` · project `{doc['project']}`", "",
             f"Exit code: **{doc['exit_code']}**" + (f" ({doc['state']})" if doc.get("state") else ""), ""]
    if doc["mode"] == "inventory":
        lines += ["> Inventory only: no MCP connection was made. Nothing here proves runtime health.", ""]
    counts = {}
    for r in (r for r in doc["results"] if not r.get("informational") or r["layer"] == "native"):
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    lines += ["Outcomes: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())), ""]
    if doc["proof"]:
        lines += ["## Strongest proof per server", "",
                  "Configured → Discoverable → Connected → Smoke passed (native-client proof separate)", "",
                  "| Client | Server | Proof | Native client |", "| --- | --- | --- | --- |"]
        lines += [f"| {p['client']} | {p['server']} | {p['proof']} | {p['native_client']} |" for p in doc["proof"]]
        lines.append("")
    attention = [r for r in doc["results"] if r["outcome"] != "passed"
                 and (not r.get("informational") or (r["layer"] == "native" and r["outcome"] in ("failed", "auth_required")))]
    lines += ["## Needs attention", ""]
    if not attention:
        lines += ["None.", ""]
    for r in attention:
        who = f"{r['client']}/{r['server']}" if r.get("server") else r["client"]
        lines.append(f"- **{r['outcome']}** · {who} · {r['layer']} · {r['check']}: {r['detail']}")
        if r.get("next_action"):
            lines.append(f"  - Next: {r['next_action']}")
        if r.get("diagnostics"):
            lines.append(f"  - Diagnostics: `{r['diagnostics']}`")
    lines += ["", "## All results", "", "| Outcome | Client | Server | Layer | Check |", "| --- | --- | --- | --- | --- |"]
    lines += [f"| {r['outcome']} | {r['client']} | {r.get('server') or ''} | {r['layer']} | {r['check']} |"
              for r in doc["results"]]
    lines += ["", "## Limitations", "", f"- {SANITIZER_LIMITATIONS}",
              "- Plugin-provided and claude.ai connector servers are not resolved from files.",
              "- A direct SDK connection is not the same as a call through the real agent client.",
              "- The SDK starts stdio servers with a restricted default environment plus the configured env; "
              "clients may pass more. SSE-only remotes are probed as streamable HTTP.",
              "- A server child that calls setsid and double-forks before cleanup escapes it; SIGKILL of the "
              "doctor itself orphans its worker.",
              "- Every probe and CLI check runs in its own session, which is killed when the check ends; helper daemons a client starts on purpose die with it.",
              "- Recycled-pid risk is limited by re-checking each pid's process group before a second signal."]
    return "\n".join(lines) + "\n"


def write(out_dir: Path, doc: dict, scrub, leaks=lambda text: []) -> tuple[str, str]:
    """Serialise, scrub, gate, and write. Returns (json_text, markdown_text)."""
    created = not out_dir.exists()
    out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if created:
        os.chmod(out_dir, 0o700)   # never change the mode of a directory the user pointed us at
    json_text = json.dumps(doc, indent=2)   # strings were scrubbed leaf-by-leaf by the caller
    md_text = scrub(markdown(doc))
    if leaks(json_text + md_text):
        # Keep the run's outcome visible, drop every free-text field.
        for row in doc["results"]:
            row["detail"], row["next_action"] = "[withheld: sanitizer gate]", ""
        doc["servers"] = [{k: v for k, v in s.items() if k in ("client", "server", "enabled", "transport")}
                          for s in doc["servers"]]
        json_text = json.dumps(doc, indent=2)
        md_text = markdown(doc)
        if leaks(json_text + md_text):
            raise PermissionError("sanitizer failed to remove a registered secret; nothing was written")
    for name, text in (("result.json", json_text), ("summary.md", md_text)):
        path = out_dir / name
        path.write_text(text)
        os.chmod(path, 0o600)
    return json_text, md_text


def default_output_dir(env: dict) -> Path:
    base = env.get("XDG_STATE_HOME") or os.path.join(env.get("HOME", str(Path.home())), ".local/state")
    stamp = now().replace(":", "").replace("-", "").replace("+0000", "Z").replace("+00:00", "Z")
    return Path(base) / "ai-tools-doctor" / stamp
