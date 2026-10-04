# Native binary installation only; client declarations belong to shdots.
# Immutable v0.11.0 release, commit 8972ea69c6ad94b1ef1d4ffbf0a92d78d2db1798.
# SHA-256 values match both upstream checksums.txt and GitHub asset digests:
# https://github.com/DeusData/codebase-memory-mcp/releases/tag/v0.11.0
install_codebase_memory() (
  set -eu
  version=0.11.0
  target="$HOME/.local/bin/codebase-memory-mcp"
  if [ -x "$target" ] && [ "$("$target" --version)" = "codebase-memory-mcp $version" ]; then
    return 0
  fi

  os=$(uname -s)
  arch=$(uname -m)
  case "$arch" in
    arm64|aarch64) arch=arm64 ;;
    x86_64|amd64)
      arch=amd64
      # A Rosetta shell must still install the native Apple Silicon binary.
      if [ "$os" = Darwin ] && [ "$(sysctl -n hw.optional.arm64 2>/dev/null || :)" = 1 ]; then
        arch=arm64
      fi
      ;;
    *) echo "codebase-memory-mcp: unsupported architecture: $arch" >&2; return 1 ;;
  esac
  case "$os/$arch" in
    Darwin/arm64) platform=darwin-arm64; digest=4dee7f38b63740e6751d7a7ed7eb10291c1f2a3ea2415f599dc68370ca0a2d18 ;;
    Darwin/amd64) platform=darwin-amd64; digest=dbf1c73bfcbde64e7dde4cd1320da7afc02e2c972ee1789ae039521411f5132e ;;
    Linux/arm64) platform=linux-arm64-portable; digest=d62eeb224d5ee3eba3070938ec62cf1033f10b041ec1c4b2fb67f7aef390cc7b ;;
    Linux/amd64) platform=linux-amd64-portable; digest=1f9e8293eb2bc5c05cfa27a7e8fc033da6d729ffad525ccfcdaa3fd606306683 ;;
    *) echo "codebase-memory-mcp: unsupported platform: $os/$arch" >&2; return 1 ;;
  esac

  umask 077
  tmp=$(mktemp -d "${TMPDIR:-/tmp}/shdots-cbm.XXXXXX") || return 1
  restore_rc=false
  had_rc=false
  cleanup() {
    # The binary's install command appends to .zshrc even with --skip-config.
    # Preserve managed content, permissions, and the originally absent case.
    if [ "$restore_rc" = true ]; then
      if [ "$had_rc" = true ]; then
        cp -p "$tmp/zshrc" "$HOME/.zshrc" || return 1
      else
        rm -f "$HOME/.zshrc" || return 1
      fi
    fi
    rm -rf "$tmp"
  }
  trap 'cleanup || exit 1' EXIT
  trap 'exit 1' HUP INT TERM

  archive="codebase-memory-mcp-$platform.tar.gz"
  curl --proto '=https' --proto-redir '=https' --tlsv1.2 -fsSL \
    --connect-timeout 15 --max-time 180 \
    "https://github.com/DeusData/codebase-memory-mcp/releases/download/v$version/$archive" \
    -o "$tmp/$archive" || return 1
  if command -v sha256sum >/dev/null 2>&1; then
    actual=$(sha256sum "$tmp/$archive" | awk '{print $1}')
  elif command -v shasum >/dev/null 2>&1; then
    actual=$(shasum -a 256 "$tmp/$archive" | awk '{print $1}')
  else
    echo "codebase-memory-mcp: SHA-256 verification tool required" >&2
    return 1
  fi
  if [ "$actual" != "$digest" ]; then
    echo "codebase-memory-mcp: checksum mismatch; refusing installation" >&2
    return 1
  fi

  # Extract only the verified binary. Never execute/copy the bundled install.sh.
  tar -xzf "$tmp/$archive" -C "$tmp" codebase-memory-mcp || return 1
  candidate="$tmp/codebase-memory-mcp"
  [ -f "$candidate" ] && [ ! -L "$candidate" ] || return 1
  chmod 755 "$candidate" || return 1
  if [ "$os" = Darwin ]; then
    xattr -d com.apple.quarantine "$candidate" >/dev/null 2>&1 || :
    codesign --sign - --force "$candidate" || return 1
  fi
  [ "$("$candidate" --version)" = "codebase-memory-mcp $version" ] || return 1

  if [ -e "$HOME/.zshrc" ]; then
    cp -p "$HOME/.zshrc" "$tmp/zshrc" || return 1
    had_rc=true
  fi
  restore_rc=true
  SHELL=/bin/zsh "$candidate" install -y --force --skip-config "--dir=$HOME/.local/bin" || return 1
  [ "$("$target" --version)" = "codebase-memory-mcp $version" ]
)
