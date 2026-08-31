#!/usr/bin/env bash
# Launch a dev VM from provision/dev-vm-cloud-init.yaml.
#
# The CPUS/MEMORY/DISK/IMAGE defaults below are the fleet standard, one spec for
# every dev box. See AGENTS.md "Dev VM spec" before changing a default vs. passing
# a one-off --cpus/--memory/--disk flag for a single launch.
#
# One cloud-init serves every dev box; this script fills in the two things that differ:
# the VM's name and the launching Host's own SSH public key (so each VM trusts the Mac
# that created it — ~/.ssh/id_ed25519.pub if present, else ~/.ssh/id_rsa.pub;
# override with --pubkey or $DEV_VM_PUBKEY).
#
#   ./launch-dev-vm.sh as-dev                              # personal VM (defaults below)
#   ./launch-dev-vm.sh fdx-dev                             # work VM, same spec
#   ./launch-dev-vm.sh as-dev --dry-run                    # print the plan, launch nothing
#
# Post-launch steps are interactive and live in provision/README.md; the script prints
# them on success.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$SCRIPT_DIR/dev-vm-cloud-init.yaml"

VM_NAME=""
CPUS=6
MEMORY=12G
DISK=220G
IMAGE=24.04
PUBKEY="${DEV_VM_PUBKEY:-}"
DRY_RUN=0

die() { printf 'error: %s\n' "$1" >&2; exit 1; }

usage() {
  awk 'NR>1 && /^#/ { sub(/^# ?/, ""); print; next } NR>1 { exit }' "${BASH_SOURCE[0]}"
  cat <<'USAGE'

Options:
  --cpus N          vCPUs                          (default: 6)
  --memory SIZE     RAM, e.g. 12G                  (default: 12G)
  --disk SIZE       disk ceiling, e.g. 220G        (default: 220G; qemu allocates sparsely)
  --image NAME      multipass image                (default: 24.04)
  --pubkey PATH     Host public key to authorize   (default: $DEV_VM_PUBKEY, else
                    ~/.ssh/id_ed25519.pub, else ~/.ssh/id_rsa.pub)
  --dry-run         print the rendered cloud-init and the multipass command, then exit
  -h, --help        this message
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --cpus)    CPUS="${2:?--cpus needs a value}";    shift 2 ;;
    --memory)  MEMORY="${2:?--memory needs a value}"; shift 2 ;;
    --disk)    DISK="${2:?--disk needs a value}";    shift 2 ;;
    --image)   IMAGE="${2:?--image needs a value}";  shift 2 ;;
    --pubkey)  PUBKEY="${2:?--pubkey needs a value}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    -*)        die "unknown option: $1 (try --help)" ;;
    *)
      [ -z "$VM_NAME" ] || die "unexpected argument: $1 (one VM name only)"
      VM_NAME="$1"; shift ;;
  esac
done

[ -n "$VM_NAME" ] || { usage; exit 1; }
case "$VM_NAME" in
  *[!a-zA-Z0-9-]*) die "VM name must be alphanumeric with dashes: '$VM_NAME'" ;;
esac
[ -f "$TEMPLATE" ] || die "template not found: $TEMPLATE"
if [ "$DRY_RUN" -eq 0 ]; then
  command -v multipass >/dev/null 2>&1 || die "multipass not on PATH (brew install --cask multipass)"
fi

# --- resolve the Host public key ---------------------------------------------------
if [ -z "$PUBKEY" ]; then
  for candidate in "$HOME/.ssh/id_ed25519.pub" "$HOME/.ssh/id_rsa.pub"; do
    [ -f "$candidate" ] && PUBKEY="$candidate" && break
  done
fi
[ -n "$PUBKEY" ] || die "no Host public key found; pass --pubkey PATH or set \$DEV_VM_PUBKEY"
[ -f "$PUBKEY" ] || die "public key not readable: $PUBKEY"
case "$PUBKEY" in
  *.pub) ;;
  *) die "refusing to use '$PUBKEY': expected a .pub file, not a private key" ;;
esac
KEY_LINE="$(head -n1 "$PUBKEY")"
case "$KEY_LINE" in
  ssh-*|ecdsa-*|sk-ssh-*|sk-ecdsa-*) ;;
  *) die "'$PUBKEY' does not look like an OpenSSH public key" ;;
esac

if [ "$DRY_RUN" -eq 0 ] && multipass info "$VM_NAME" >/dev/null 2>&1; then
  die "instance '$VM_NAME' already exists — 'multipass delete --purge $VM_NAME' first, or pick another name"
fi

# --- render ------------------------------------------------------------------------
RENDERED="$(mktemp -t "${VM_NAME}-cloud-init")"
trap 'rm -f "$RENDERED"' EXIT

# awk's gsub treats \ and & in the replacement specially; escape them so an unusual
# key comment can't corrupt the output.
esc() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/&/\\\&/g'; }

BH_KEY="$(esc "$KEY_LINE")" BH_NAME="$(esc "$VM_NAME")" awk '
  { gsub(/@@HOST_SSH_PUBKEY@@/, ENVIRON["BH_KEY"])
    gsub(/@@VM_NAME@@/,         ENVIRON["BH_NAME"])
    print }
' "$TEMPLATE" > "$RENDERED"

if grep -q '@@[A-Z_]*@@' "$RENDERED"; then
  grep -n '@@[A-Z_]*@@' "$RENDERED" >&2
  die "unsubstituted placeholders remain (template and script are out of sync)"
fi

printf 'name       %s\n' "$VM_NAME"
printf 'image      %s\n' "$IMAGE"
printf 'resources  %s cpu / %s ram / %s disk\n' "$CPUS" "$MEMORY" "$DISK"
printf 'host key   %s\n' "$PUBKEY"
printf '\n'

set -- multipass launch "$IMAGE" \
  --name "$VM_NAME" \
  --cpus "$CPUS" \
  --memory "$MEMORY" \
  --disk "$DISK" \
  --cloud-init "$RENDERED" \
  --timeout 1800

if [ "$DRY_RUN" -eq 1 ]; then
  echo '--- rendered cloud-init ---'
  cat "$RENDERED"
  echo '--- command (not run) ---'
  printf '%s ' "$@"; printf '\n'
  exit 0
fi

# package_update + package_upgrade routinely outrun multipass's default timeout.
# Don't die under set -e on a nonzero exit: a timeout usually means the VM is
# still provisioning, not that it failed — check before rebuilding.
LAUNCH_RC=0
"$@" || LAUNCH_RC=$?
if [ "$LAUNCH_RC" -ne 0 ]; then
  printf '\nmultipass launch exited %s — the VM may still be provisioning.\n' "$LAUNCH_RC"
  printf 'Check with: multipass exec %s -- cloud-init status --wait\n' "$VM_NAME"
fi

cat <<EOF

$VM_NAME is up. cloud-init finished the unattended half; these need you:

  1. tailscale   multipass shell $VM_NAME
                 sudo tailscale up --ssh --hostname=$VM_NAME    # browser auth
                 sudo tailscale set --auto-update
  2. age key     ssh $VM_NAME 'mkdir -p ~/.config/chezmoi'
                 scp ~/.config/chezmoi/key.txt $VM_NAME:~/.config/chezmoi/key.txt
  3. ssh keys    personal VM:  ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_personal
                 work VM:      generate BOTH id_ed25519_foodics AND id_ed25519_personal
                 (the managed ssh config offers the personal key to github.com on
                 work VMs too). Add each .pub to its GitHub as BOTH an authentication
                 and a signing key, then append to dot_config/git/allowed_signers
  4. token       export GITHUB_TOKEN=...              # current shell, for step 5
                 echo 'export GITHUB_TOKEN=...' >> ~/.zshrc.local   # persist
                 (else mise install 403s partway)
  5. chezmoi     sh -c "\$(curl -fsLS get.chezmoi.io/lb)" -- init --apply shahwan42/shdots
  6. firewall    sudo ufw enable   # only after confirming 'multipass shell $VM_NAME' works

Full detail and verification checks: provision/README.md
EOF
