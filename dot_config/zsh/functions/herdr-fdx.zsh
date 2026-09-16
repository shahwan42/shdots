# Connect to fdx-dev or fdx-host, preferring local network with tailnet fallback.
# Usage: herdr-fdx-dev [herdr options]   # 192.168.252.3
#        herdr-fdx-host [herdr options]  # 192.168.100.147
if (( $+commands[timeout] )); then
  herdr-fdx-dev() {
    local local_ip="192.168.252.3" timeout_secs=5
    print "herdr-fdx-dev: trying local network ($local_ip)..."
    timeout $timeout_secs command herdr --remote "ubuntu@$local_ip" "$@"
    local exit_code=$?

    if (( exit_code == 124 )); then
      print "herdr-fdx-dev: local timeout, falling back to tailnet..."
      command herdr --remote fdx-dev "$@"
    elif (( exit_code != 0 )); then
      print "herdr-fdx-dev: local failed, falling back to tailnet..."
      command herdr --remote fdx-dev "$@"
    fi
  }

  herdr-fdx-host() {
    local local_ip="192.168.100.147" timeout_secs=5
    print "herdr-fdx-host: trying local network ($local_ip)..."
    timeout $timeout_secs command herdr --remote "as@$local_ip" "$@"
    local exit_code=$?

    if (( exit_code == 124 )); then
      print "herdr-fdx-host: local timeout, falling back to tailnet..."
      command herdr --remote fdx-host "$@"
    elif (( exit_code != 0 )); then
      print "herdr-fdx-host: local failed, falling back to tailnet..."
      command herdr --remote fdx-host "$@"
    fi
  }
fi
