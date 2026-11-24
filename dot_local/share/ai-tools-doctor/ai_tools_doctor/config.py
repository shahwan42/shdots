"""Configuration inspection: resolved MCP server declarations per client.

Claude has no resolved export, so only the necessary sections of
~/.claude.json, .mcp.json and settings are read.
Every secret-bearing value is registered with the redactor on read.
"""
from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path

from .context import Context
from .model import ServerConfig, result

ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


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


READERS = {"claude": read_claude}
