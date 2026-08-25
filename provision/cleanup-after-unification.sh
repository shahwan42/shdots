#!/usr/bin/env bash
# One-time cleanup after the mise/chezmoi unification.
# Removes tools/files now provided by mise or chezmoi externals, so the machine
# stops carrying duplicate copies from Homebrew/apt/curl.
#
# SAFE BY DEFAULT: dry-run. Review the output, then re-run with --apply.
#   ./cleanup-after-unification.sh            # prints what it would do
#   ./cleanup-after-unification.sh --apply    # actually removes
#
# Never touches the keep-native set (GNU coreutils, services, PHP/iOS stack,
# GUI apps, security tools). Anything it can't classify is listed for you.

set -uo pipefail
APPLY=0; [ "${1:-}" = "--apply" ] && APPLY=1
run() { if [ "$APPLY" -eq 1 ]; then echo "+ $*"; "$@"; else echo "would: $*"; fi; }

# Formulae/packages moved to mise — remove the Homebrew/apt copies.
# NOTE: btop stays native on the Mac (mise's aqua btop is linux-only), so it is
# deliberately absent from this list.
BREW_REMOVE=(
  awscli bat eza fd fzf gh git-delta gitleaks jq lazygit neovim ripgrep starship
  zoxide zsh-autosuggestions zsh-completions zsh-syntax-highlighting
  actionlint alexsjones/llmfit/llmfit cmake commitizen csvlens deno direnv
  glow harlequin herdr jesseduffield/lazydocker/lazydocker jira-cli lazysql mark
  mycli node node@22 fnm pgcli pygments ranger sonar-scanner
  tealdeer uv watchexec yazi yt-dlp zellij
  colima           # retiring (user decision 2026-08-25)
  tailscale        # provided by the tailscale-app cask
)
# NOT removed: chezmoi and mise. On an existing machine the brew copy may be the
# ONLY chezmoi present — uninstalling it strands the machine. Fresh machines
# bootstrap both via curl and never have a brew copy. Leave them be.
# fdx-dev (Ubuntu) residuals from the dev-env setup, now owned by mise/externals.
APT_REMOVE=(fd-find ripgrep fzf zoxide zsh-autosuggestions zsh-syntax-highlighting)
BIN_SYMLINKS=(
  "$HOME/.local/bin/fd"        # symlink to fdfind
  "$HOME/.local/bin/starship"  # curl-installed
  "$HOME/.local/bin/herdr"     # curl-installed (now mise)
)

echo "=== cleanup-after-unification ($([ "$APPLY" -eq 1 ] && echo APPLY || echo DRY-RUN)) ==="

case "$(uname -s)" in
  Darwin)
    if command -v brew >/dev/null 2>&1; then
      installed="$(brew list --formula 2>/dev/null)"
      for f in "${BREW_REMOVE[@]}"; do
        name="${f##*/}"
        if echo "$installed" | grep -qx "$name"; then
          run brew uninstall --ignore-dependencies "$f"
        fi
      done
      echo "--- colima note: 'brew uninstall colima' does NOT delete ~/.colima;"
      echo "    remove that dir manually once you've confirmed nothing needs it."
    fi
    ;;
  Linux)
    for p in "${APT_REMOVE[@]}"; do
      if dpkg -s "$p" >/dev/null 2>&1; then run sudo apt-get remove -y "$p"; fi
    done
    for l in "${BIN_SYMLINKS[@]}"; do
      [ -e "$l" ] && run rm -f "$l"
    done
    # The manually-installed Neovim (mise now provides neovim).
    [ -L /usr/local/bin/nvim ] && run sudo rm -f /usr/local/bin/nvim
    [ -d /opt/nvim-linux-arm64 ] && run sudo rm -rf /opt/nvim-linux-arm64
    echo "--- kept on the VM: php8.3* apt modules (herdr/native PHP), docker, zsh."
    ;;
esac

# oh-my-zsh remnants (already purged on the work Mac; harmless if absent).
[ -d "$HOME/.oh-my-zsh" ] && run rm -rf "$HOME/.oh-my-zsh"

# Report brew leaves not in the remove list and not obviously keep-native, so you
# can decide. (macOS only; informational.)
if [ "$(uname -s)" = Darwin ] && command -v brew >/dev/null 2>&1; then
  echo "=== brew leaves still present — review any unexpected entries ==="
  brew leaves 2>/dev/null | while read -r leaf; do
    skip=0
    for r in "${BREW_REMOVE[@]}"; do [ "${r##*/}" = "$leaf" ] && skip=1 && break; done
    [ "$skip" -eq 0 ] && echo "  keep/review: $leaf"
  done
fi

echo "=== done ($([ "$APPLY" -eq 1 ] && echo applied || echo dry-run; )) ==="
