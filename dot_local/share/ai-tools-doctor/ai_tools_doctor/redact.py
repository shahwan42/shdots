"""Redaction: collect secret values from configuration, then scrub every output.

Safe fields are extracted by allowlist elsewhere; this module is the second
layer. It scrubs known secret values, token-shaped strings, credential-bearing
URLs and URIs, and ``--flag=value`` credential arguments from any text.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

MASK = "[REDACTED]"
MIN_SECRET_LENGTH = 6
BENIGN_VALUES = {"true", "false", "null", "none", "info", "debug", "warn", "error", "http", "https", "stdio",
                 "localhost", "127.0.0.1", "production", "development", "default", "enabled", "disabled"}

TOKEN_PATTERNS = [
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{8,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{8,}"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{8,}"),
    re.compile(r"\bAKIA[0-9A-Z]{12,}"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]*"),
    re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=\-]{8,}"),
    re.compile(r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{8,}"),
    re.compile(r"\bglpat-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\bnpm_[A-Za-z0-9]{16,}"),
    re.compile(r"\bAIza[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bhf_[A-Za-z0-9]{16,}"),
    re.compile(r"\bya29\.[A-Za-z0-9_\-]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.S),
]
# scheme://user:password@host — keeps the scheme and host, drops the credentials.
USERINFO = re.compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.\-]*://)[^\s/@]*@")
DATABASE_URI = re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://\S+", re.I)
URL_QUERY = re.compile(r"(?P<base>https?://[^\s?#\"']+)\?[^\s\"']*")
CREDENTIAL_FLAG = re.compile(
    r"(?i)(?P<flag>--?[a-z0-9_-]*(?:password|passwd|token|secret|api[-_]?key|private[-_]?key|dsn|credential|"
    r"auth(?:orization)?|bearer)[a-z0-9_-]*(?:=|\s+))(?P<value>\S+)")
HEADER_LINE = re.compile(
    r"(?i)(?P<q>[\"']?)\b(?P<name>[a-z0-9-]*(?:authorization|api-key|auth-token|cookie|secret|token))(?P=q)"
    r"\s*[:=]\s*[\"']?[^\r\n\"']+")
SECRET_FLAG = re.compile(r"(?i)^--?[a-z0-9_-]*(?:password|passwd|token|secret|api[-_]?key|private[-_]?key|dsn|credential|auth(?:orization)?|bearer)[a-z0-9_-]*$")


class Redactor:
    def __init__(self) -> None:
        self._secrets: set[str] = set()
        self.limitations: list[str] = []

    def add(self, value: object) -> None:
        """Register a secret value so every later occurrence is masked."""
        if not isinstance(value, str) or len(value) < MIN_SECRET_LENGTH or value.lower() in BENIGN_VALUES:
            return
        self._secrets.add(value)
        if value.startswith("Bearer "):
            self.add(value[7:])

    def add_url(self, url: str) -> None:
        """Register credential-bearing parts of a URL."""
        try:
            parts = urlsplit(url)
        except ValueError:
            self.add(url)
            return
        if parts.username:
            self.add(parts.username)
        if parts.password:
            self.add(parts.password)
        for segment in parts.path.split("/"):
            if len(segment) >= 8 and segment.lower() not in ("mcp", "api", "v1", "v2", "sse", "stream"):
                self.add(segment)
        if parts.fragment:
            self.add(parts.fragment)
        if parts.query:
            self.add(parts.query)
            for pair in parts.query.split("&"):
                self.add(pair.partition("=")[2])

    def add_arguments(self, args: list[str]) -> None:
        """Register arguments; the item after a credential-looking flag is itself a secret."""
        for index, arg in enumerate(args):
            self.add_argument(arg)
            if index and SECRET_FLAG.match(args[index - 1]) and "=" not in args[index - 1]:
                self.add(arg)

    def add_argument(self, arg: str) -> None:
        """Register credential-shaped command arguments (URIs with userinfo, flag values)."""
        if USERINFO.search(arg) or DATABASE_URI.search(arg):
            self.add_url(arg)
            self.add(arg)
        for found in TOKEN_PATTERNS:
            for match in found.findall(arg):
                self.add(match)
        match = CREDENTIAL_FLAG.search(arg)
        if match:
            self.add(match.group("value"))
        if SECRET_FLAG.match(arg.partition("=")[0]) and "=" in arg:
            self.add(arg.partition("=")[2])

    def scrub(self, text: str) -> str:
        if not text:
            return text
        for secret in sorted(self._secrets, key=len, reverse=True):
            text = text.replace(secret, MASK)
        text = DATABASE_URI.sub(MASK, text)
        text = USERINFO.sub(lambda m: m.group("scheme") + MASK + "@", text)
        text = URL_QUERY.sub(lambda m: m.group("base") + "?" + MASK, text)
        text = HEADER_LINE.sub(lambda m: m.group("q") + m.group("name") + m.group("q") + ": " + MASK, text)
        text = CREDENTIAL_FLAG.sub(lambda m: m.group("flag") + MASK, text)
        for pattern in TOKEN_PATTERNS:
            text = pattern.sub(MASK, text)
        return text

    def scrub_data(self, value):
        """Scrub every string in a JSON-compatible structure, keys included."""
        if isinstance(value, str):
            return self.scrub(value)
        if isinstance(value, list):
            return [self.scrub_data(item) for item in value]
        if isinstance(value, dict):
            return {self.scrub(str(k)): self.scrub_data(v) for k, v in value.items()}
        return value

    def leaks(self, text: str) -> list[int]:
        """Return the lengths of registered secrets still present in text, raw or JSON-escaped
        (output gate; never returns the secret itself)."""
        import json
        return [len(s) for s in self._secrets if s in text or json.dumps(s)[1:-1] in text]


def origin(url: str) -> str:
    """scheme://host[:port] only — no path, userinfo or query."""
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
        return f"{parts.scheme}://{host}{port}" if parts.scheme and host else "[unparseable-url]"
    except ValueError:
        return "[unparseable-url]"


def tilde(path: str, home: str) -> str:
    return "~" + path[len(home):] if home and path.startswith(home + "/") else path
