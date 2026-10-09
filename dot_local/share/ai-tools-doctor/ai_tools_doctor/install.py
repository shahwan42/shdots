"""Installation ownership: selected executable, candidates, version, expected owner."""
from __future__ import annotations

import os
import re
import errno
from pathlib import Path

from . import proc
from .context import CLIENTS, Context
from .model import result
from .redact import tilde

BINARY = {"codex": "codex", "claude": "claude", "opencode": "opencode"}
EXPECTED = {
    "mac": {"codex": "homebrew", "claude": "native", "opencode": "mise"},
    "vm": {"codex": "mise", "claude": "mise", "opencode": "mise"},
}
OWNER_FIX = {
    "homebrew": "Install with Homebrew (see Brewfile): brew install --cask codex",
    "native": "Install with the vendor native installer: curl -fsSL https://claude.ai/install.sh | bash",
    "mise": "Declare it in dot_config/mise/config.toml.tmpl and run: chezmoi apply",
}
VERSION_TOKEN = r"v?\d+(?:\.\d+){1,3}(?:[-+][0-9A-Za-z][0-9A-Za-z.+-]*)?"
VERSION_PREFIXES = {"codex": ("codex", "codex cli"), "claude": ("claude", "claude code"),
                    "opencode": ("opencode",)}


def approved_version(text: str, tool: str) -> str | None:
    """Accept only a known client label followed by a version token."""
    prefixes = VERSION_PREFIXES.get(tool, ())
    for line in text.splitlines()[:10]:
        if len(line) > 256:
            continue
        for prefix in prefixes:
            match = re.fullmatch(rf"\s*{re.escape(prefix)}\s+(?:version\s+)?({VERSION_TOKEN})\s*", line,
                                 re.IGNORECASE)
            if match:
                return match.group(1).removeprefix("v")
            # Claude Code currently also labels the product after the version.
            match = re.fullmatch(rf"\s*({VERSION_TOKEN})\s+\({re.escape(prefix)}\)\s*", line, re.IGNORECASE)
            if match:
                return match.group(1).removeprefix("v")
    return None


def classify(tool: str, lexical: str, real: str, home: str) -> str:
    if "/mise/" in lexical or "/mise/" in real:
        return "mise"
    if real.startswith(("/opt/homebrew/", "/usr/local/Cellar/", "/usr/local/Caskroom/", "/usr/local/Homebrew/")) \
            or "/Caskroom/" in real or "/Cellar/" in real:
        return "homebrew"
    if lexical.startswith("/opt/homebrew/bin/") or lexical.startswith("/usr/local/bin/") and "Cellar" in real:
        return "homebrew"
    if tool == "claude" and (real.startswith(home + "/.local/share/claude/")
                             or lexical == home + "/.local/bin/claude"):
        return "native"
    if real.startswith("/Applications/") or ".app/Contents" in real:
        return "app-bundled"
    return "other"


def path_candidates(tool: str, env: dict, home: str) -> tuple[list[str], set[str]]:
    seen, found = set(), []
    for directory in (env.get("PATH") or "").split(os.pathsep):
        if not directory:
            continue
        candidate = os.path.join(directory, BINARY[tool])
        if candidate not in seen and os.path.isfile(candidate) | os.path.islink(candidate):
            seen.add(candidate)
            found.append(candidate)
    on_path = set(found)
    extras = [f"/opt/homebrew/bin/{tool}", f"{home}/.local/bin/{tool}", f"{home}/.local/share/mise/shims/{tool}"]
    mise_installs = Path(home) / ".local/share/mise/installs"
    for pattern in (f"{tool}/*/{tool}", f"npm-*{tool}*/*/bin/{tool}", f"*{tool}*/*/{tool}", f"*{tool}*/*/bin/{tool}"):
        extras += [str(p) for p in sorted(mise_installs.glob(pattern))]
    for candidate in extras:
        if candidate not in seen and (os.path.isfile(candidate) or os.path.islink(candidate)):
            seen.add(candidate)
            found.append(candidate)
    return found, on_path


def project_mise_config(project: str, home: str) -> str | None:
    cur = Path(project)
    for directory in [cur, *cur.parents]:
        for name in ("mise.toml", ".mise.toml", ".tool-versions", "mise.local.toml"):
            if (directory / name).is_file() and str(directory) != home:
                return str(directory / name)
        if str(directory) == home:
            break
    return None


def version_of(ctx: Context, path: str) -> dict:
    """Parse only an approved version token; never return command output or exception text."""
    out = proc.run([path, "--version"], timeout=15, env=ctx.env, cwd=ctx.project)
    if out.spawn_error:
        reason = "executable_not_found" if out.spawn_errno == errno.ENOENT else \
            "permission_denied" if out.spawn_errno in (errno.EACCES, errno.EPERM) else "version_command_start_failed"
        return {"version": None, "reason_code": reason, "elapsed_ms": out.elapsed_ms}
    if out.timed_out:
        return {"version": None, "reason_code": "timeout", "elapsed_ms": out.elapsed_ms}
    if out.returncode != 0:
        return {"version": None, "reason_code": "version_command_failed", "exit_code": out.returncode,
                "elapsed_ms": out.elapsed_ms}
    version = approved_version(out.stdout, Path(path).name.lower())
    return {"version": version, "reason_code": None if version else "unparseable_version",
            "elapsed_ms": out.elapsed_ms}


def check_tool(ctx: Context, tool: str) -> tuple[list[dict], dict]:
    """Return result rows and a tool record {selected, path, version, owner, candidates}."""
    expected = EXPECTED[ctx.kind][tool]
    candidates, on_path = path_candidates(tool, ctx.env, ctx.home)
    prov = f"PATH scan; profile kind={ctx.kind} role={ctx.role} ({ctx.profile_source})"
    mise_note = None
    selected = next((c for c in candidates if c in on_path), None)   # only a PATH entry can be "selected"
    override = project_mise_config(ctx.project, ctx.home)
    if override and selected and classify(tool, selected, os.path.realpath(selected), ctx.home) == "mise":
        which = proc.run(["mise", "which", BINARY[tool]], timeout=15, env=ctx.env, cwd=ctx.project)
        if which.returncode == 0 and which.stdout.strip():
            chosen = which.stdout.strip().splitlines()[0]
            if expected == "mise" and chosen != selected \
                    and classify(tool, chosen, os.path.realpath(chosen), ctx.home) == "mise":
                mise_note = f"project mise override in {tilde(override, ctx.home)} selects {tilde(chosen, ctx.home)}"
                prov += f"; {mise_note}"
    record = {"tool": tool, "expected_owner": expected,
              "candidates": [], "selected": None, "version": None, "owner": None}
    others = []
    for cand in candidates:
        real = os.path.realpath(cand)
        owner = classify(tool, cand, real, ctx.home)
        record["candidates"].append({"path": tilde(cand, ctx.home), "resolved": tilde(real, ctx.home),
                                     "owner": owner, "selected": cand == selected})
        if cand != selected:
            others.append(owner)
    rows = []
    if not selected:
        where = f" Installed but not on PATH: {', '.join(tilde(c, ctx.home) for c in candidates[:3])}." \
            if candidates else ""
        rows.append(result(client=tool, check="installation", layer="installation", outcome="failed",
                           detail=f"{BINARY[tool]} not found on PATH.{where}",
                           next_action=OWNER_FIX.get(expected, ""), provenance=prov,
                           reason_code="not_on_path" if candidates else "executable_not_found"))
        return rows, record
    real = os.path.realpath(selected)
    owner = classify(tool, selected, real, ctx.home)
    check = version_of(ctx, selected)
    version, problem = check["version"], check["reason_code"]
    record.update(selected=tilde(selected, ctx.home), resolved=tilde(real, ctx.home), owner=owner, version=version)
    versions = {tool: version} if version else {}
    if not os.path.exists(real) or problem:
        explanations = {
            "executable_not_found": "executable was not found",
            "permission_denied": "permission was denied",
            "version_command_start_failed": "version command could not start",
            "timeout": "version check timed out after 15 seconds",
            "version_command_failed": f"version command exited with code {check.get('exit_code')}",
            "unparseable_version": "version output did not match an approved version format",
        }
        rows.append(result(client=tool, check="installation", layer="installation", outcome="failed",
                           reason_code=problem or "executable_not_found",
                           detail=f"Selected {tilde(selected, ctx.home)} ({owner}) does not run: "
                                  f"{explanations.get(problem, 'version check failed')}.",
                           next_action=f"Repair the {expected} installation: {OWNER_FIX.get(expected, '')}",
                           provenance=prov, versions=versions, elapsed_ms=check["elapsed_ms"],
                           **({"exit_code": check["exit_code"]} if "exit_code" in check else {})))
    elif owner != expected and not mise_note:
        rows.append(result(client=tool, check="installation", layer="installation", outcome="failed",
                           reason_code="unexpected_owner",
                           detail=f"Selected {tilde(selected, ctx.home)} is owned by {owner}; "
                                  f"expected {expected} on {ctx.kind}.",
                           next_action=f"Fix PATH order or reinstall via {expected}; do not delete other copies "
                                       f"without review. {OWNER_FIX.get(expected, '')}",
                           provenance=prov, versions=versions, elapsed_ms=check["elapsed_ms"]))
    else:
        extra = f" Inactive copies: {', '.join(sorted(set(others)))}." if others else ""
        rows.append(result(client=tool, check="installation", layer="installation", outcome="passed",
                           detail=f"{tilde(selected, ctx.home)} ({owner}) runs; version {version}.{extra} "
                                  "Proves the executable starts, not MCP or model health.",
                           provenance=prov, versions=versions, elapsed_ms=check["elapsed_ms"]))
    return rows, record


def inventory(ctx: Context, clients) -> tuple[list[dict], dict]:
    rows, records = [], {}
    for tool in clients:
        r, rec = check_tool(ctx, tool)
        rows += r
        records[tool] = rec
    return rows, records
