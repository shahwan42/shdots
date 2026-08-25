#!/bin/sh
# Bootstrap mise if absent — cross-platform, no Homebrew dependency.
# chezmoi installs the repo first (its own curl installer); this brings up the
# toolchain manager before any managed file that expects it.
set -eu

if command -v mise >/dev/null 2>&1 || [ -x "$HOME/.local/bin/mise" ]; then
  exit 0
fi

echo "mise not found — installing via https://mise.run"
curl -fsSL https://mise.run | sh
