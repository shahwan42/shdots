"""Execution context: account, environment, project and redaction state."""
from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path

from . import proc
from .redact import Redactor

CLIENTS = ("codex", "claude", "opencode")


@dataclass
class Context:
    home: str
    env: dict
    project: str
    kind: str          # mac | vm
    role: str          # personal | work | unknown
    redactor: Redactor = field(default_factory=Redactor)
    profile_source: str = "unknown"
    notes: list = field(default_factory=list)

    def scrub(self, text: str) -> str:
        return self.redactor.scrub(text)


def detect_profile(env: dict, override_kind: str | None, override_role: str | None) -> tuple[str, str, str]:
    """Return (kind, role, source). Read-only: `chezmoi data` renders without applying."""
    if override_kind or override_role:
        return override_kind or "mac", override_role or "unknown", "command line"
    out = proc.run(["chezmoi", "data", "--format", "json"], timeout=15, env=env)
    if out.returncode == 0:
        try:
            data = json.loads(out.stdout)
            kind = data.get("kind")
            if kind in ("mac", "vm"):
                role = data.get("role") or "unknown"
                return kind, role, "chezmoi data"
        except json.JSONDecodeError:
            pass
    kind = "mac" if platform.system() == "Darwin" else "vm"
    return kind, "unknown", "platform fallback (chezmoi data unavailable)"


def build(project: str | None, kind: str | None = None, role: str | None = None,
          env: dict | None = None) -> Context:
    env = dict(os.environ if env is None else env)
    home = env.get("HOME") or str(Path.home())
    k, r, source = detect_profile(env, kind, role)
    return Context(home=home, env=env, project=str(Path(project or os.getcwd()).resolve()),
                   kind=k, role=r, profile_source=source)
