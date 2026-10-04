source "$1"
fixture=${2:A}
source "$3"
production=$4
host_ostype=$OSTYPE
zmodload zsh/stat
zstat -H metadata -- "$fixture/brew"
brew_uid=$metadata[uid]
_test_audit_uid=$(( brew_uid + 10000 ))
HOMEBREW_PREFIX=$fixture/brew
OSTYPE=darwin
system_fpath=( $fpath )
die() { print -u2 -r -- "FAIL: $*"; exit 1; }
pass() { print -r -- "PASS: $*"; }
# Capture decisions while retaining the actual compaudit/stat/resolution code.
compinit() { decision="$*"; }

fpath=("$fixture/secure" "$fixture/empty-parent/missing" "$fixture/brew/share/zsh/site-functions" $system_fpath)
before=$(compaudit 2>/dev/null)
[[ $before == *"$fixture/empty-parent"* ]] || die 'missing fpath fixture did not reproduce parent finding'
_shdots_compinit
[[ $fpath[1] == "$fixture/secure" && $fpath[2] == "$fixture/brew/share/zsh/site-functions" ]] || die 'missing fpath filtering/order'
[[ ${fpath[(Ie)"$fixture/empty-parent/missing"]} == 0 ]] || die 'missing fpath retained'
pass 'missing fpath removed; existing directories retained in order'

fpath=("$fixture/insecure" $system_fpath)
_shdots_compinit
[[ $fpath[1] == "$fixture/insecure" && -z $decision ]] || die 'existing insecure directory silently accepted'
[[ $(compaudit 2>/dev/null) == *"$fixture/insecure"* ]] || die 'existing insecure directory not detected'
pass 'existing insecure directory retained and detected by real compaudit'

trust_check() {
  local entry=$1 expected=$2 result=reject
  _shdots_trusted_cask_completion "$entry" "${HOMEBREW_PREFIX:A}" "$brew_uid" && result=trust
  [[ $result == $expected ]] || die "$entry expected=$expected actual=$result"
  pass "${entry:t}: $result (real resolution/stat)"
}
trust_check "$fixture/brew/share/zsh/site-functions/_app" trust
for name in tmp work-home brew-home other-prefix non-bundle broken; do
  trust_check "$fixture/brew/share/zsh/site-functions/_$name" reject
done
trust_check "$fixture/outside-link" reject
trust_check "$fixture/ordinary" reject
trust_check "$fixture/brew/share/zsh/site-functions/_root-target" reject

# Different ownership cannot be created without sudo. Delegate every stat to
# the builtin and alter only one selected uid in its result, including lstat.
zstat() {
  builtin zstat "$@" || return
  if [[ ${@[-1]} == $unexpected_path ]]; then
    _stat[uid]=$(( brew_uid + 20000 ))
  fi
}
unexpected_path=$fixture/brew/share/zsh/site-functions/_app
trust_check "$unexpected_path" reject
fpath=("$fixture/brew/share/zsh/site-functions" $system_fpath)
compaudit() { print -r -- "$unexpected_path"; }
_shdots_compinit
[[ -z $decision ]] || die 'wrapper accepted unexpected symlink owner'
source "$3"
pass 'unexpected symlink owner rejected'
unexpected_path=$fixture/Applications/Example.app/Contents/Resources/zsh/site-functions/_example
trust_check "$fixture/brew/share/zsh/site-functions/_app" reject
pass 'unexpected target owner rejected'
unexpected_path=$fixture/Applications/Example.app/Contents
trust_check "$fixture/brew/share/zsh/site-functions/_app" reject
pass 'unexpected bundle-chain owner rejected'
unexpected_path=$fixture/brew/share/zsh
trust_check "$fixture/brew/share/zsh/site-functions/_app" reject
pass 'unexpected Homebrew directory owner rejected'
unfunction zstat

chmod 777 "$fixture/Applications/Example.app/Contents"
trust_check "$fixture/brew/share/zsh/site-functions/_app" reject
chmod 755 "$fixture/Applications/Example.app/Contents"
pass 'writable bundle component rejected'

# Root ownership of an external target cannot exempt an escaping Brew link.
compaudit() { print -r -- "$fixture/brew/share/zsh/site-functions/_root-target"; }
_shdots_compinit
[[ -z $decision ]] || die 'escaping link accepted solely because target is root-owned'
source "$3"
pass 'root-owned external non-bundle target rejected by wrapper'

# Drive the wrapper through real compaudit with just the approved fixture link.
for file in "$fixture/brew/share/zsh/site-functions"/_*(N); do
  [[ ${file:t} == _app ]] || rm "$file"
done
fpath=("$fixture/brew/share/zsh/site-functions" $system_fpath)
_shdots_compinit
[[ $decision == -u ]] || die 'approved app finding did not select trusted initialization'
pass 'real compaudit + approved app selects trusted initialization'
ln -s "$fixture/tmp/_outside" "$fixture/brew/share/zsh/site-functions/_unsafe"
_shdots_compinit
[[ -z $decision ]] || die 'mixed approved/unapproved findings bypassed audit'
pass 'one untrusted finding preserves normal compinit checking'
rm "$fixture/brew/share/zsh/site-functions/_unsafe"
OSTYPE=linux-gnu
_shdots_compinit
[[ -z $decision ]] || die 'macOS exception used on Linux'
pass 'application exception is macOS only'

# Best-effort host check: fixed production policy, actual Homebrew/Ghostty
# metadata, and the installed compaudit algorithm with a non-maintainer UID.
ghostty=/opt/homebrew/share/zsh/site-functions/_ghostty
if [[ $host_ostype == darwin* && -L $ghostty && -f $ghostty && -x /opt/homebrew/bin/brew ]]; then
  OSTYPE=darwin
  source "$production"
  HOMEBREW_PREFIX=/opt/homebrew
  zstat -H metadata -- "$HOMEBREW_PREFIX"
  _shdots_trusted_cask_completion "$ghostty" "${HOMEBREW_PREFIX:A}" "$metadata[uid]" || die 'actual Ghostty rejected'
  pass 'host Ghostty production predicate (real ownership/modes)'
  fpath=(/opt/homebrew/share/zsh/site-functions $system_fpath)
  _shdots_compinit
  [[ $decision == -u ]] || die 'actual host completion findings would prompt for another account'
  [[ ${fpath[(Ie)/usr/local/share/zsh/site-functions]} == 0 || -d /usr/local/share/zsh/site-functions ]] || die 'host missing path retained'
  pass 'host shared-install audit selects trusted startup without missing fpath'
else
  print 'SKIP: host Ghostty completion is absent'
fi
