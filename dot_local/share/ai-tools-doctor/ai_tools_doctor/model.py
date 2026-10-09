"""Shared result vocabulary and server configuration records."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re

OUTCOMES = ("passed", "failed", "unverified", "auth_required", "timeout", "skipped")
LAYERS = ("installation", "configuration", "skills", "discovery", "connection", "tools", "smoke", "native")
# Strongest established proof for a server, weakest first.
PROOF_ORDER = ("none", "configured", "discoverable", "connected", "smoke_passed")
LAUNCHERS = {"npx", "bunx", "pnpx", "uvx", "pipx", "dlx"}
LAUNCHER_WITH_SUBCOMMAND = {("npm", "exec"), ("npm", "x"), ("pnpm", "dlx"), ("pnpm", "exec"), ("yarn", "dlx"),
                            ("bun", "x"), ("uv", "tool"), ("deno", "run")}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_package_launcher(command: str | None, args: list[str]) -> bool:
    """True when the command would fetch and run a package (installing dependencies)."""
    if not command:
        return False
    name = command.rsplit("/", 1)[-1]
    if name in LAUNCHERS:
        return True
    return bool(args) and (name, args[0]) in LAUNCHER_WITH_SUBCOMMAND


@dataclass
class ServerConfig:
    """A configured MCP server. `private` never leaves memory; `safe()` is the only export."""
    client: str
    name: str
    enabled: bool
    transport: str  # stdio | http | sse | unknown
    provenance: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    forwarded_env: list[str] = field(default_factory=list)
    cwd: str | None = None
    auth: str | None = None          # client-reported authentication metadata, if any
    approval: str | None = None      # project trust/approval state, if any
    unresolved: list[str] = field(default_factory=list)  # references that could not be resolved
    tool_restrictions: dict = field(default_factory=dict)  # {"allow": [...], "deny": [...]} when known
    notes: list[str] = field(default_factory=list)

    @property
    def key(self) -> tuple[str, str]:
        return (self.client, self.name)

    @property
    def launcher(self) -> bool:
        return self.transport == "stdio" and is_package_launcher(self.command, self.args)

    def safe(self, home: str, origin_fn, tilde_fn) -> dict:
        record = {
            "client": self.client, "server": self.name, "enabled": self.enabled,
            "transport": self.transport, "provenance": self.provenance,
            "env_keys": sorted(self.env) + sorted(self.forwarded_env),
            "header_keys": sorted(self.headers),
        }
        credential_names = sorted({key for key, value in [*self.env.items(), *self.headers.items()]
                                   if value and re.search(r"(?i)(token|secret|password|passwd|credential|api[-_]?key|auth|uri|url|dsn|pat)", key)})
        if credential_names:
            record["credential_values_present"] = credential_names
        if self.command:
            record["command"] = tilde_fn(self.command, home) if "/" in self.command else self.command
            record["arg_count"] = len(self.args)
            record["package_launcher"] = self.launcher
        if self.url:
            record["url_origin"] = origin_fn(self.url)
        for key in ("auth", "approval"):
            if getattr(self, key):
                record[key] = getattr(self, key)
        if self.unresolved:
            record["unresolved_references"] = sorted(set(self.unresolved))
        if self.tool_restrictions:
            record["tool_restrictions"] = self.tool_restrictions
        if self.notes:
            record["notes"] = self.notes
        return record


def result(*, client: str, check: str, layer: str, outcome: str, detail: str, next_action: str = "",
           server: str | None = None, provenance: str = "", versions: dict | None = None, **extra) -> dict:
    assert outcome in OUTCOMES and layer in LAYERS, (outcome, layer)
    row = {"client": client, "server": server, "check": check, "layer": layer, "outcome": outcome,
           "detail": detail, "next_action": next_action, "provenance": provenance,
           "versions": versions or {}, "timestamp": now()}
    row.update(extra)
    if outcome in ("failed", "timeout", "auth_required", "unverified"):
        row.setdefault("reason_code", {
            "failed": "unexpected_failure",
            "timeout": "timeout",
            "auth_required": "authentication_required",
            "unverified": "proof_unavailable",
        }[outcome])
    return row
