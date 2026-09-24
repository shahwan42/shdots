#!/usr/bin/env bash
# Launch a dev VM from provision/dev-vm-cloud-init.yaml. The Multipass launcher:
# provision/new-box calls this, and it is also usable standalone.
#
# The CPUS/MEMORY/DISK/IMAGE defaults below are the fleet standard, one spec for
# every dev box. See AGENTS.md "Dev VM spec" before changing a default vs. passing
# a one-off --cpus/--memory/--disk flag for a single launch.
#
# One cloud-init serves every dev box; this script fills in what differs per launch:
# the VM's name, both workstations' SSH public keys (read from .chezmoidata/fleet.yaml
# — every dev box trusts both Macs, not just the one that launched it), and
# MAC_ACCESS=gateway (this is the Multipass launcher, so the Mac-bridge firewall
# allow rule in the cloud-init is always on here; a future VPS launcher would leave
# it "none").
#
#   ./launch-dev-vm.sh as-dev                              # personal VM (defaults below)
#   ./launch-dev-vm.sh fdx-dev                             # work VM, same spec
#   ./launch-dev-vm.sh as-dev --dry-run                    # print the plan, launch nothing
#
# Post-launch: provision/new-box drives cloud-init wait, key seeding, GitHub SSH-key
# registration, and chezmoi init non-interactively. See provision/README.md for the
# manual fallback and verification checks.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$SCRIPT_DIR/dev-vm-cloud-init.yaml"
FLEET_YAML="$SCRIPT_DIR/../.chezmoidata/fleet.yaml"

VM_NAME=""
CPUS=6
MEMORY=12G
DISK=220G
IMAGE=24.04
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
[ -f "$FLEET_YAML" ] || die "fleet data not found: $FLEET_YAML"
if [ "$DRY_RUN" -eq 0 ]; then
  command -v multipass >/dev/null 2>&1 || die "multipass not on PATH (brew install --cask multipass)"
fi

# --- resolve both workstation public keys from .chezmoidata/fleet.yaml -------------
extract_key() {
  awk -F': *' -v k="$1" '$1 ~ "^[[:space:]]*"k"$" { gsub(/"/, "", $2); print $2; exit }' "$FLEET_YAML"
}
AS_HOST_KEY="$(extract_key as_host)"
FDX_HOST_KEY="$(extract_key fdx_host)"
[ -n "$AS_HOST_KEY" ] || die "as_host key not found in $FLEET_YAML"
[ -n "$FDX_HOST_KEY" ] || die "fdx_host key not found in $FLEET_YAML"
for key in "$AS_HOST_KEY" "$FDX_HOST_KEY"; do
  case "$key" in
    ssh-*|ecdsa-*|sk-ssh-*|sk-ecdsa-*) ;;
    *) die "fleet.yaml key does not look like an OpenSSH public key: '$key'" ;;
  esac
done

if [ "$DRY_RUN" -eq 0 ] && multipass info "$VM_NAME" >/dev/null 2>&1; then
  die "instance '$VM_NAME' already exists — 'multipass delete --purge $VM_NAME' first, or pick another name"
fi

# --- render ------------------------------------------------------------------------
RENDERED="$(mktemp -t "${VM_NAME}-cloud-init")"
trap 'rm -f "$RENDERED"' EXIT

# awk's gsub treats \ and & in the replacement specially; escape them so an unusual
# key comment can't corrupt the output.
esc() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/&/\\\&/g'; }

BH_AS_KEY="$(esc "$AS_HOST_KEY")" BH_FDX_KEY="$(esc "$FDX_HOST_KEY")" BH_NAME="$(esc "$VM_NAME")" awk '
  { gsub(/@@AS_HOST_PUBKEY@@/,  ENVIRON["BH_AS_KEY"])
    gsub(/@@FDX_HOST_PUBKEY@@/, ENVIRON["BH_FDX_KEY"])
    gsub(/@@MAC_ACCESS@@/,      "gateway")
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
printf 'authorized as_host, fdx_host (from .chezmoidata/fleet.yaml)\n'
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

$VM_NAME is up. cloud-init finished the unattended half, including ufw (with the
Mac-bridge allow rule) and chrony. Called from provision/new-box, the rest — age key,
ssh-keygen -R, an SSH key generated on the box, GitHub registration, and a
non-interactive chezmoi init --apply — is automated; run that instead of the manual
steps below.

Manual fallback, if not using new-box:

  1. age key     ssh -o BatchMode=yes ubuntu@$VM_NAME.local 'mkdir -p ~/.config/chezmoi'
                 scp ~/.config/chezmoi/key.txt ubuntu@$VM_NAME.local:~/.config/chezmoi/key.txt
  2. ssh key     ssh ubuntu@$VM_NAME.local 'ssh-keygen -t ed25519 -N "" -C $VM_NAME -f ~/.ssh/id_ed25519'
                 Add the .pub to GitHub as BOTH an authentication and a signing key
                 (github.foodics.com too for a work box) — see provision/new-box.
  3. chezmoi     ssh ubuntu@$VM_NAME.local
                 sh -c "\$(curl -fsLS get.chezmoi.io/lb)" -- init --apply shahwan42/shdots

Full detail and verification checks: provision/README.md
EOF
