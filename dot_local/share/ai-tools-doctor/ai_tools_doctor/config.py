"""Configuration inspection: resolved MCP server declarations per client.

Codex and OpenCode expose resolved exports; Claude lacks one, so only the
necessary sections of ~/.claude.json, .mcp.json and settings are read.
Every secret-bearing value is registered with the redactor on read.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import tomllib
from pathlib import Path

from . import proc
from .context import Context
from .model import ServerConfig, result

ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")
OC_ENV_REF = re.compile(r"\{env:([A-Za-z_][A-Za-z0-9_]*)\}")


def _register(ctx: Context, cfg: ServerConfig) -> None:
    for value in [*cfg.env.values(), *cfg.headers.values()]:
        ctx.redactor.add(value)
        if value.lower().startswith("bearer "):
            ctx.redactor.add(value[7:])
    ctx.redactor.add_arguments(cfg.args)
    for name in cfg.forwarded_env:
        ctx.redactor.add(ctx.env.get(name))
    if cfg.url:
        ctx.redactor.add_url(cfg.url)
    if cfg.command:
        ctx.redactor.add_argument(cfg.command)


def _expand(text, pattern, lookup, cfg: ServerConfig):
    if not isinstance(text, str):
        return text
    def sub(match):
        value = lookup(match)
        if value is None:
            cfg.unresolved.append(match.group(1))
            return match.group(0)
        return value
    return pattern.sub(sub, text)


CREDENTIAL_KEY = re.compile(r"(?i)(token|secret|password|passwd|credential|api[-_]?key|auth|uri|url|dsn|pat)")


def _flag_empty_credentials(cfg: ServerConfig) -> None:
    """An empty credential makes some servers fall back to an interactive login (e.g. a browser
    launch). Never start a server whose credential-like value is empty."""
    for key, value in [*cfg.env.items(), *cfg.headers.items()]:
        if value == "" and CREDENTIAL_KEY.search(key):
            cfg.unresolved.append(f"{key} (empty)")


def _finish(ctx: Context, cfg: ServerConfig, expander=None) -> ServerConfig:
    if expander:
        cfg.command = expander(cfg.command, cfg)
        cfg.args = [expander(a, cfg) for a in cfg.args]
        cfg.url = expander(cfg.url, cfg)
        cfg.env = {k: expander(v, cfg) for k, v in cfg.env.items()}
        cfg.headers = {k: expander(v, cfg) for k, v in cfg.headers.items()}
    _flag_empty_credentials(cfg)
    _register(ctx, cfg)
    return cfg


# ---- Codex ---------------------------------------------------------------

def codex_trust(ctx: Context) -> str:
    path = Path(ctx.home) / ".codex/config.toml"
    try:
        projects = tomllib.loads(path.read_text()).get("projects", {})
    except (OSError, tomllib.TOMLDecodeError):
        return "unknown (codex config unreadable)"
    for candidate in [Path(ctx.project), *Path(ctx.project).parents]:
        level = projects.get(str(candidate), {}).get("trust_level")
        if level:
            return f"{level} ({'project' if candidate == Path(ctx.project) else 'ancestor'})"
    return "no trust record"


def codex_restrictions(ctx: Context) -> dict:
    """Tool allow/deny lists from the user config ($CODEX_HOME) and, when present, the project config."""
    merged: dict = {}
    home = Path(ctx.env.get("CODEX_HOME") or Path(ctx.home) / ".codex")
    for path in (home / "config.toml", Path(ctx.project) / ".codex/config.toml"):
        try:
            data = tomllib.loads(path.read_text())
        except (OSError, tomllib.TOMLDecodeError):
            continue
        for name, s in data.get("mcp_servers", {}).items():
            entry = {k: v for k, v in (("allow", s.get("enabled_tools")), ("deny", s.get("disabled_tools"))) if v}
            if entry:
                merged.setdefault(name, {}).update(entry)
    return merged


def read_codex(ctx: Context) -> tuple[list[ServerConfig], list[dict]]:
    out = proc.run(["codex", "mcp", "list", "--json"], timeout=15, env=ctx.env, cwd=ctx.project)
    prov = f"codex mcp list --json (cwd={ctx.project}); project trust: {codex_trust(ctx)}"
    if out.returncode != 0 or out.spawn_error or out.timed_out:
        reason = out.spawn_error or ("timed out" if out.timed_out else f"exit {out.returncode}")
        return [], [result(client="codex", check="config export", layer="configuration", outcome="unverified",
                           detail=f"codex mcp list --json unavailable: {ctx.scrub(reason)}",
                           next_action="Repair the Codex installation first (installation row).", provenance=prov)]
    try:
        items = json.loads(out.stdout)
    except json.JSONDecodeError:
        return [], [result(client="codex", check="config export", layer="configuration", outcome="unverified",
                           detail="codex mcp list --json did not return JSON.", provenance=prov)]
    restrictions = codex_restrictions(ctx)
    servers = []
    for item in items:
        t = item.get("transport") or {}
        kind = t.get("type")
        cfg = ServerConfig(client="codex", name=item["name"], enabled=item.get("enabled", True) is not False,
                           transport="stdio" if kind == "stdio" else "http" if kind in ("streamable_http", "http")
                           else "sse" if kind == "sse" else "unknown",
                           provenance=prov, auth=item.get("auth_status"),
                           tool_restrictions=restrictions.get(item["name"], {}))
        if item.get("disabled_reason"):
            cfg.notes.append(f"disabled: {item['disabled_reason']}")
        if cfg.transport == "stdio":
            cfg.command, cfg.args = t.get("command"), list(t.get("args") or [])
            cfg.env = {k: str(v) for k, v in (t.get("env") or {}).items()}
            cfg.forwarded_env = list(t.get("env_vars") or [])
            cfg.cwd = t.get("cwd")
        else:
            cfg.url = t.get("url")
            cfg.headers = {k: str(v) for k, v in (t.get("http_headers") or {}).items()}
            for header, var in (t.get("env_http_headers") or {}).items():
                if ctx.env.get(var):
                    cfg.headers[header] = ctx.env[var]
                else:
                    cfg.unresolved.append(var)
            bearer = t.get("bearer_token_env_var")
            if bearer:
                if ctx.env.get(bearer):
                    cfg.headers["Authorization"] = f"Bearer {ctx.env[bearer]}"
                else:
                    cfg.unresolved.append(bearer)
            if t.get("http_headers_helper"):
                cfg.unresolved.append("http_headers_helper")
        servers.append(_finish(ctx, cfg))
    return servers, []


# ---- OpenCode ------------------------------------------------------------

def read_opencode(ctx: Context) -> tuple[list[ServerConfig], list[dict]]:
    out = proc.run(["opencode", "debug", "config"], timeout=15, env=ctx.env, cwd=ctx.project)
    prov = f"opencode debug config (resolved, cwd={ctx.project})"
    data = None
    if out.returncode == 0 and not out.timed_out:
        start = out.stdout.find("{")
        try:
            data = json.loads(out.stdout[start:]) if start >= 0 else None
        except json.JSONDecodeError:
            data = None
    if data is None:
        reason = out.spawn_error or ("timed out" if out.timed_out else f"exit {out.returncode}")
        return [], [result(client="opencode", check="config export", layer="configuration", outcome="unverified",
                           detail=f"opencode debug config unavailable: {ctx.scrub(str(reason))}",
                           next_action="Repair the OpenCode installation first (installation row).", provenance=prov)]
    def lookup(match):
        return ctx.env.get(match.group(1))
    def expander(value, cfg):
        return _expand(value, OC_ENV_REF, lookup, cfg)
    tools_map = data.get("tools") or {}
    denied = {k for k, v in tools_map.items() if v is False}
    enabled_overrides = [k for k, v in tools_map.items() if v is True]
    servers = []
    for name, item in (data.get("mcp") or {}).items():
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        cfg = ServerConfig(client="opencode", name=name, enabled=item.get("enabled", True) is not False,
                           transport="stdio" if kind == "local" else "http" if kind == "remote" else "unknown",
                           provenance=prov)
        mine = sorted(k for k in denied if k == "*" or k == name or k.startswith(f"{name}_")
                      or fnmatch.fnmatch(f"{name}_probe", k))
        if mine:
            cfg.tool_restrictions = {"deny": mine, "allow_override": [k for k in enabled_overrides
                                                                      if k.startswith(f"{name}_")]}
        if data.get("permission"):
            cfg.notes.append("OpenCode permission rules are not interpreted for tool restrictions")
        if cfg.transport == "stdio":
            command = list(item.get("command") or [])
            cfg.command, cfg.args = (command[0] if command else None), command[1:]
            cfg.env = {k: str(v) for k, v in (item.get("environment") or {}).items()}
        else:
            cfg.url = item.get("url")
            cfg.headers = {k: str(v) for k, v in (item.get("headers") or {}).items()}
            if item.get("oauth") is not False and not cfg.headers:
                cfg.auth = "client-owned OAuth possible"
        servers.append(_finish(ctx, cfg, expander))
    return servers, []


# ---- Claude --------------------------------------------------------------

def _claude_server(ctx: Context, name: str, item: dict, scope: str, approval: str | None, enabled=True):
    def lookup(match):
        value = ctx.env.get(match.group(1))
        return value if value is not None else match.group(2)
    def expander(value, cfg):
        return _expand(value, ENV_REF, lookup, cfg)
    kind = item.get("type") or ("stdio" if item.get("command") else "http" if item.get("url") else "unknown")
    cfg = ServerConfig(client="claude", name=name, enabled=enabled,
                       transport="stdio" if kind == "stdio" else "http" if kind == "http"
                       else "sse" if kind == "sse" else "unknown",
                       provenance=f"claude {scope}", approval=approval)
    cfg.command, cfg.args = item.get("command"), list(item.get("args") or [])
    cfg.env = {k: str(v) for k, v in (item.get("env") or {}).items()}
    cfg.url = item.get("url")
    cfg.headers = {k: str(v) for k, v in (item.get("headers") or {}).items()}
    if item.get("headersHelper"):
        cfg.unresolved.append("headersHelper")
    return _finish(ctx, cfg, expander)


def claude_denied(ctx: Context) -> list[str]:
    denied = []
    for path in (Path(ctx.home) / ".claude/settings.json", Path(ctx.home) / ".claude/settings.local.json",
                 Path(ctx.project) / ".claude/settings.json", Path(ctx.project) / ".claude/settings.local.json"):
        try:
            denied += json.loads(path.read_text()).get("permissions", {}).get("deny", [])
        except (OSError, json.JSONDecodeError):
            pass
    return sorted({d for d in denied if isinstance(d, str) and d.startswith("mcp__")})


def claude_enable_all(ctx: Context) -> bool:
    for path in (Path(ctx.home) / ".claude/settings.json", Path(ctx.home) / ".claude/settings.local.json",
                 Path(ctx.project) / ".claude/settings.json", Path(ctx.project) / ".claude/settings.local.json"):
        try:
            if json.loads(path.read_text()).get("enableAllProjectMcpServers") is True:
                return True
        except (OSError, json.JSONDecodeError):
            pass
    return False


def read_claude(ctx: Context) -> tuple[list[ServerConfig], list[dict]]:
    path = Path(ctx.home) / ".claude.json"
    rows, servers = [], []
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [], [result(client="claude", check="config read", layer="configuration", outcome="unverified",
                           detail=f"~/.claude.json unreadable: {type(exc).__name__}",
                           next_action="Start Claude Code once to create its configuration.",
                           provenance="~/.claude.json")]
    section = (data.get("projects") or {}).get(ctx.project, {})
    disabled = set(section.get("disabledMcpServers") or [])
    for name, item in (data.get("mcpServers") or {}).items():
        servers.append(_claude_server(ctx, name, item, "user scope (~/.claude.json mcpServers)", None,
                                      name not in disabled))
    for name, item in (section.get("mcpServers") or {}).items():
        servers.append(_claude_server(ctx, name, item, f"local scope (~/.claude.json projects[{ctx.project}])",
                                      None, name not in disabled))
    approved, rejected = set(section.get("enabledMcpjsonServers") or []), set(section.get("disabledMcpjsonServers") or [])
    # Project scope: the project directory, then ancestors only while inside $HOME (never beyond it).
    inside_home = Path(ctx.project).is_relative_to(ctx.home)
    ancestors = [Path(ctx.project)] + ([p for p in Path(ctx.project).parents if p.is_relative_to(ctx.home)]
                                       if inside_home else [])
    for directory in ancestors:
        mcp_json = directory / ".mcp.json"
        if mcp_json.is_file():
            try:
                items = json.loads(mcp_json.read_text()).get("mcpServers", {})
            except (OSError, json.JSONDecodeError):
                items = {}
            for name, item in items.items():
                auto = claude_enable_all(ctx) and name not in rejected
                approval = "approved" if name in approved or auto else "rejected" if name in rejected \
                    else "pending approval"
                servers.append(_claude_server(ctx, name, item, f"project scope ({mcp_json})", approval,
                                              approval == "approved"))
        if str(directory) == ctx.home:
            break
    denied = claude_denied(ctx)
    for cfg in servers:
        mine = [d for d in denied if d == f"mcp__{cfg.name}" or d.startswith(f"mcp__{cfg.name}__")
                or fnmatch.fnmatch(f"mcp__{cfg.name}__x", d)]
        if mine:
            cfg.tool_restrictions = {"deny": mine}
    # Claude precedence is local > project > user: one winner per name; shadowed copies are noted.
    rank = lambda c: 0 if c.provenance.startswith("claude local") else 1 if c.provenance.startswith("claude project") else 2
    winners: dict[str, ServerConfig] = {}
    for cfg in sorted(servers, key=lambda c: (not c.enabled, rank(c))):   # a usable definition beats a pending one
        if cfg.name in winners:
            winners[cfg.name].notes.append(f"shadows a {cfg.provenance.split(' (')[0]} definition")
        else:
            winners[cfg.name] = cfg
    servers = list(winners.values())
    rows.append(result(client="claude", check="config coverage", layer="configuration", outcome="unverified",
                       detail="Plugin-provided, claude.ai connector and managed-policy servers are not resolved "
                              "from files; only user, local and project (.mcp.json) scopes were read.",
                       next_action="Use `claude mcp get <name>` under --probe for any server missing here.",
                       provenance="~/.claude.json, .mcp.json, settings.json", informational=True))
    return servers, rows


READERS = {"codex": read_codex, "claude": read_claude, "opencode": read_opencode}
