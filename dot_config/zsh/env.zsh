# Shared session environment — sourced by BOTH ~/.zprofile (login) and the top
# of ~/.zshrc (so et/non-login interactive shells get the identical set).
# Everything here must be idempotent: login shells run it twice.

# Agent shells keep zsh's useful defaults except for the bash-style command
# failures seen in shell tools: unmatched globs pass through and =word is text.
if [[ -n ${CLAUDECODE:-} || ${AI_AGENT:-} == claude-code_*_agent ||
      -n ${CODEX_THREAD_ID:-} ]]; then
  setopt nonomatch noequals
  typeset -g _SHDOTS_AGENT_SHELL=1
fi

# Homebrew (macOS or Linuxbrew) — probe known prefixes; no-op if absent or
# already evaluated (HOMEBREW_PREFIX set by an earlier pass).
if [[ -z ${HOMEBREW_PREFIX:-} ]]; then
  for _brew in /opt/homebrew/bin/brew /usr/local/bin/brew /home/linuxbrew/.linuxbrew/bin/brew; do
    [[ -x "$_brew" ]] && eval "$("$_brew" shellenv)" && break
  done
  unset _brew
fi

# path_helper runs after .zshenv in login shells. Restore Homebrew precedence
# even when that earlier pass already discovered its prefix (no brew subprocess).
if [[ -n ${HOMEBREW_PREFIX:-} && -x "$HOMEBREW_PREFIX/bin/brew" ]]; then
  path=("$HOMEBREW_PREFIX/bin" "$HOMEBREW_PREFIX/sbin" $path)
fi

export EDITOR=nvim
export VISUAL=nvim

# User executables precede Homebrew; mise shims precede user executables.
# Last prepend wins; typeset -U below keeps only the first occurrence.
if [[ -d "$HOME/.composer/vendor/bin" ]]; then
  path=("$HOME/.composer/vendor/bin" $path)
fi

# kitty.app ships its `kitten` / `kitty` CLIs inside the bundle and never puts
# them on PATH. Add them on macOS so `kitten ssh`, `kitten icat`, etc. resolve
# from any shell. No-op on machines without the bundle (Linux VMs).
if [[ -d "/Applications/kitty.app/Contents/MacOS" ]]; then
  path=($path "/Applications/kitty.app/Contents/MacOS")
fi

# pnpm global binaries. Pin PNPM_HOME to one XDG location on every machine
# (overrides pnpm's per-OS default, e.g. ~/Library/pnpm on macOS) so global
# installs and this PATH entry always agree. pnpm >=9 uses $PNPM_HOME/bin as
# the global bin dir; adding it unconditionally is fine — pnpm/mkdir on first
# `pnpm add -g`, and typeset -U below drops the dup on the second (login) pass.
export PNPM_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/pnpm"
path=("$PNPM_HOME/bin" $path)
[[ -d "$HOME/.local/bin" ]] && path=("$HOME/.local/bin" $path)
[[ -d "$HOME/.local/share/mise/shims" ]] && path=("$HOME/.local/share/mise/shims" $path)

typeset -U path PATH

if [[ -d /Library/Java/JavaVirtualMachines/zulu-17.jdk/Contents/Home ]]; then
  export JAVA_HOME=/Library/Java/JavaVirtualMachines/zulu-17.jdk/Contents/Home
fi
