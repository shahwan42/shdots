# Shared session environment — sourced by BOTH ~/.zprofile (login) and the top
# of ~/.zshrc (so et/non-login interactive shells get the identical set).
# Everything here must be idempotent: login shells run it twice.

# Homebrew (macOS or Linuxbrew) — probe known prefixes; no-op if absent or
# already evaluated (HOMEBREW_PREFIX set by an earlier pass).
if [[ -z ${HOMEBREW_PREFIX:-} ]]; then
  for _brew in /opt/homebrew/bin/brew /usr/local/bin/brew /home/linuxbrew/.linuxbrew/bin/brew; do
    [[ -x "$_brew" ]] && eval "$("$_brew" shellenv)" && break
  done
  unset _brew
fi

export EDITOR=nvim
export VISUAL=nvim

# Composer before ~/.local/bin so ~/.local/bin ends up in front in every mode
# (zsh arrays: last prepend wins; typeset -U keeps the front occurrence).
if [[ -d "$HOME/.composer/vendor/bin" ]]; then
  path=("$HOME/.composer/vendor/bin" $path)
fi
if [[ -d "$HOME/.local/bin" ]]; then
  path=("$HOME/.local/bin" $path)
fi
typeset -U path PATH

if [[ -d /Library/Java/JavaVirtualMachines/zulu-17.jdk/Contents/Home ]]; then
  export JAVA_HOME=/Library/Java/JavaVirtualMachines/zulu-17.jdk/Contents/Home
fi
