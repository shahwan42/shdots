# Shared Homebrew is maintained by a different account on native Macs.
# Keep compinit's normal safety behavior unless every audit finding is trusted.
_shdots_compinit() {
  emulate -L zsh
  autoload -Uz compaudit compinit
  zmodload -F zsh/stat b:zstat 2>/dev/null || { compinit; return; }

  local _audit _entry _prefix=${HOMEBREW_PREFIX:-} _brew_uid=''
  local -A _stat
  local -a _insecure _flags
  # Resolve symlinks before testing containment or ownership.
  _prefix=${_prefix:A}
  if [[ -n $_prefix && -x "$_prefix/bin/brew" ]] && \
      zstat -H _stat -- "$_prefix" 2>/dev/null; then
    _brew_uid=$_stat[uid]
  fi

  _audit=$(compaudit 2>/dev/null)
  if [[ -n $_audit ]]; then
    _insecure=("${(@f)_audit}")
    _flags=(-u)
    for _entry in "${_insecure[@]}"; do
      _entry=${_entry:A}
      if ! zstat -H _stat -- "$_entry" 2>/dev/null; then
        _flags=()
        break
      fi
      # Root is trusted. The Homebrew owner is trusted only inside its prefix,
      # never for arbitrary completion paths elsewhere in the filesystem.
      if [[ $_stat[uid] != 0 ]] && \
          ! [[ -n $_brew_uid && $_stat[uid] == $_brew_uid && \
               ( $_entry == $_prefix || $_entry == "$_prefix/"* ) ]]; then
        _flags=()
        break
      fi
    done
  fi
  compinit "${_flags[@]}"
}
