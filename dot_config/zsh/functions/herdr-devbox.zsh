# Connect to a local Multipass VM without routing SSH through its Tailnet name.
# Usage: herdr-devbox [vm-name] [herdr options]
if (( $+commands[multipass] )) && (( $+commands[jq] )); then
  herdr-devbox() {
    local vm_name=as-dev ip
    if (( $# > 0 )) && [[ $1 != -* ]]; then
      vm_name=$1
      shift
    fi
    ip=$(multipass info "$vm_name" --format json 2>/dev/null |
      jq -r --arg vm "$vm_name" '.info[$vm].ipv4[0] // empty') || return 1
    if [[ -z "$ip" ]]; then
      print -u2 "herdr-devbox: no running Multipass VM found: $vm_name"
      return 1
    fi

    command herdr --remote "ubuntu@$ip" "$@"
  }
fi
