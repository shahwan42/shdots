"""Reviewed read-only smoke probes. Tool annotations never authorize a call; this registry does."""
from __future__ import annotations

import fnmatch
import json
import re

ERROR_WORDS = ("error", "does not exist", "refused", "denied", "failed", "unauthor", "bad credentials", "invalid")

PG_SQL = "SELECT 1"


def kind_for(name: str, command: str | None, args: list[str]) -> str | None:
    base = (command or "").rsplit("/", 1)[-1]
    if name == "codebase-memory-mcp" or base == "codebase-memory-mcp":
        return "codebase-memory"
    if name == "github" or base == "github-mcp-server":
        return "github"
    if "postgres" in name or base == "postgres-mcp" or any("server-postgres" in a for a in args):
        return "postgres"
    return None


def blocked_by_client(server: str, tool: str, restrictions: dict) -> str | None:
    forms = (tool, f"mcp__{server}__{tool}", f"{server}_{tool}")
    allow, deny = restrictions.get("allow") or [], restrictions.get("deny") or []
    if any(fnmatch.fnmatch(f, p) for f in forms for p in restrictions.get("allow_override") or []):
        return None
    if allow and not any(fnmatch.fnmatch(f, p) for f in forms for p in allow):
        return "client allow-list excludes the tool"
    if any(fnmatch.fnmatch(f, p) for f in forms for p in deny) or any(
            p in (f"mcp__{server}", server) for p in deny):
        return "client deny rule excludes the tool"
    return None


def _props(tool) -> tuple[dict, list]:
    schema = getattr(tool, "input_schema", None)
    if schema is None:
        schema = getattr(tool, "inputSchema", None) or {}
    return (schema.get("properties") or {}), (schema.get("required") or [])


def plan(kind: str, server: str, tools: list, args: list[str], restrictions: dict):
    """Return (tool_name, arguments, None) or (None, None, reason_unverified)."""
    by_name = {t.name: t for t in tools}
    def pick(name):
        if name not in by_name:
            return None, f"smoke tool '{name}' is not advertised"
        reason = blocked_by_client(server, name, restrictions)
        return (name, None) if not reason else (None, reason)
    if kind == "codebase-memory":
        name, why = pick("list_projects")
        if not name:
            return None, None, why
        props, required = _props(by_name[name])
        limit = props.get("limit") or {}
        if limit.get("type") != "integer" or required:
            return None, None, "list_projects schema variant unsupported (needs optional integer 'limit')"
        return name, {"limit": 1}, None
    if kind == "github":
        name, why = pick("get_me")
        if not name:
            return None, None, why
        _, required = _props(by_name[name])
        return (name, {}, None) if not required else (None, None, "get_me requires arguments (schema variant)")
    if kind == "postgres":
        for tool_name, proof in (("query", any("server-postgres" in a for a in args)),
                                 ("execute_sql", "--access-mode=restricted" in args
                                  or any(a == "--access-mode" for a in args) and "restricted" in args)):
            if tool_name in by_name:
                props, _ = _props(by_name[tool_name])
                if "sql" not in props:
                    continue
                if not proof:
                    return None, None, (f"'{tool_name}' read-only mode cannot be proven from configuration "
                                        "(needs @modelcontextprotocol/server-postgres or --access-mode=restricted)")
                name, why = pick(tool_name)
                return (name, {"sql": PG_SQL}, None) if name else (None, None, why)
        return None, None, "no supported read-only Postgres query tool advertised"
    return None, None, "no reviewed smoke probe for this server"


def judge(kind: str, content_text: str) -> str | None:
    """Return a failure reason, or None when the response is the expected shape. Content is not retained."""
    if not content_text.strip():
        return "empty response"
    lowered = content_text.lower()
    if kind == "github":
        try:
            body = json.loads(content_text)
        except json.JSONDecodeError:
            return "get_me response is not JSON"
        if not isinstance(body, dict) or not body.get("login"):
            return "get_me response has no 'login' field"
    elif kind == "postgres":
        if any(word in lowered for word in ERROR_WORDS):
            return "response reads as a database error"
        if not re.search(r"(?<![0-9A-Za-z.])1(?![0-9A-Za-z.])", content_text):
            return "SELECT 1 result did not contain the value 1"
    elif kind == "codebase-memory":
        listing = re.match(r"\s*projects:\s*\d+", content_text)
        try:
            listing = listing or isinstance(json.loads(content_text).get("projects"), list)
        except (json.JSONDecodeError, AttributeError):
            pass
        if not listing:
            return "response is not a project listing"
    return None
