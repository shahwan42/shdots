#!/bin/sh
# Bootstrap mise if absent — cross-platform, no Homebrew dependency.
# chezmoi installs the repo first (its own curl installer); this brings up the
# toolchain manager before any managed file that expects it.
# Download-then-run, not curl|sh: a failed/truncated download must fail this
# script, not silently execute half an installer.
set -eu

if command -v mise >/dev/null 2>&1 || [ -x "$HOME/.local/bin/mise" ]; then
  exit 0
fi

echo "mise not found — installing via https://mise.run"
tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
curl -fsSL https://mise.run -o "$tmp"
sh "$tmp"
command -v mise >/dev/null 2>&1 || [ -x "$HOME/.local/bin/mise" ] \
  || { echo 'mise install failed' >&2; exit 1; }
