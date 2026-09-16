# Connect to fdx-dev or fdx-host, preferring local network with tailnet fallback.
# Usage: herdr-fdx <vm-name> [herdr options]
#        herdr-fdx-dev [herdr options]
#        herdr-fdx-host [herdr options]
if (( $+commands[multipass] )) && (( $+commands[jq] )) && (( $+commands[timeout] )); then
  herdr-fdx() {
    local vm_name=$1 ip timeout_secs=8
    shift || { print -u2 "herdr-fdx: vm-name required"; return 1 }

    ip=$(multipass info "$vm_name" --format json 2>/dev/null |
      jq -r --arg vm "$vm_name" '.info[$vm].ipv4[0] // empty') || return 1

    if [[ -z "$ip" ]]; then
      print "herdr-fdx: local IP not found for $vm_name, falling back to tailnet..."
      command herdr --remote "$vm_name" "$@"
      return
    fi

    print "herdr-fdx: trying local network ($ip)..."
    timeout $timeout_secs command herdr --remote "ubuntu@$ip" "$@"
    local exit_code=$?

    if (( exit_code == 124 )); then
      print "herdr-fdx: local connection timeout, falling back to tailnet ($vm_name)..."
      command herdr --remote "$vm_name" "$@"
    elif (( exit_code != 0 )); then
      print "herdr-fdx: local connection failed, falling back to tailnet ($vm_name)..."
      command herdr --remote "$vm_name" "$@"
    fi
  }

  herdr-fdx-dev() { herdr-fdx fdx-dev "$@" }
  herdr-fdx-host() { herdr-fdx fdx-host "$@" }
fi
