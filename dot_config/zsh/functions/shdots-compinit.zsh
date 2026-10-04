# Shared Homebrew is maintained by a different account on native Macs.
# Keep compinit's normal safety behavior unless every audit finding is trusted.
_shdots_trusted_cask_completion() {
  emulate -L zsh
  local _link=${1:a} _prefix=$2 _brew_uid=$3 _target _bundle _component
  local -A _stat
  [[ -n $_brew_uid && -L $_link && -f $_link && $_link == "$_prefix/"* ]] || return 1
  # Check the link itself, then its resolved containing directories. A parent
  # symlink must not move the link outside the trusted installation.
  zstat -L -H _stat -- "$_link" 2>/dev/null || return 1
  [[ $_stat[uid] == 0 || $_stat[uid] == $_brew_uid ]] || return 1
  _component=${_link:h:A}
  [[ $_component == $_prefix || $_component == "$_prefix/"* ]] || return 1
  while true; do
    zstat -H _stat -- "$_component" 2>/dev/null || return 1
    [[ $_stat[uid] == 0 || $_stat[uid] == $_brew_uid ]] || return 1
    (( (_stat[mode] & 8#22) == 0 )) || return 1
    [[ $_component == $_prefix ]] && break
    _component=${_component:h}
  done

  _target=${_link:A}
  [[ $_target == /Applications/* ]] || return 1
  _bundle=${_target#/Applications/}
  _bundle=${_bundle%%/*}
  [[ $_bundle == ?*.app && $_target == "/Applications/$_bundle/"* ]] || return 1
  # Trust every component from the regular completion file through the bundle;
  # neither another owner nor group/world-writable content can enter this case.
  _component=$_target
  while [[ $_component != /Applications ]]; do
    zstat -H _stat -- "$_component" 2>/dev/null || return 1
    [[ $_stat[uid] == 0 || $_stat[uid] == $_brew_uid ]] || return 1
    (( (_stat[mode] & 8#22) == 0 )) || return 1
    _component=${_component:h}
  done
  # macOS's shared /Applications is normally root:admin 0775. Admin group
  # writes are expected here; world writes and unexpected owners are not.
  zstat -H _stat -- /Applications 2>/dev/null || return 1
  [[ $_stat[uid] == 0 || $_stat[uid] == $_brew_uid ]] || return 1
  (( (_stat[mode] & 8#2) == 0 &&
     ( (_stat[mode] & 8#20) == 0 || _stat[gid] == 80 ) ))
}

_shdots_compinit() {
  emulate -L zsh
  local _entry
  local -a _existing_fpath
  # Missing entries can make compaudit flag an unrelated empty parent. Keep
  # the order and every existing entry, including suspicious/broken symlinks.
  for _entry in "${fpath[@]}"; do
    [[ -e $_entry || -L $_entry ]] && _existing_fpath+=("$_entry")
  done
  fpath=("${_existing_fpath[@]}")
  autoload -Uz compaudit compinit
  zmodload -F zsh/stat b:zstat 2>/dev/null || { compinit; return; }

  local _audit _resolved _link _parent _prefix=${HOMEBREW_PREFIX:-} _brew_uid=''
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
      # A broken link must never inherit trust from its unresolved spelling.
      if [[ ! -e $_entry ]]; then
        _flags=()
        break
      fi
      _resolved=${_entry:A}
      if [[ -L $_entry ]]; then
        _link=${_entry:a}
        _parent=${_link:h:A}
        if ! zstat -L -H _stat -- "$_entry" 2>/dev/null || \
            { [[ $_stat[uid] != 0 ]] && \
              ! [[ -n $_brew_uid && $_stat[uid] == $_brew_uid && \
                   ( $_parent == $_prefix || $_parent == "$_prefix/"* ) ]]; }; then
          _flags=()
          break
        fi
        # An escaping Homebrew link must satisfy the bundle rule even when
        # its target is root-owned. Root ownership alone is not this exception.
        if [[ $_link == "$_prefix/"* && $_resolved != "$_prefix/"* && $_resolved != $_prefix ]]; then
          if [[ $OSTYPE == darwin* ]] && \
              _shdots_trusted_cask_completion "$_entry" "$_prefix" "$_brew_uid"; then
            continue
          fi
          _flags=()
          break
        fi
      fi
      if ! zstat -H _stat -- "$_resolved" 2>/dev/null; then
        _flags=()
        break
      fi
      # Root is trusted. The Homebrew owner is trusted only inside its prefix,
      # never for arbitrary completion paths elsewhere in the filesystem.
      if [[ $_stat[uid] != 0 ]] && \
          ! [[ -n $_brew_uid && $_stat[uid] == $_brew_uid && \
               ( $_resolved == $_prefix || $_resolved == "$_prefix/"* ) ]]; then
        _flags=()
        break
      fi
    done
  fi
  compinit "${_flags[@]}"
}
