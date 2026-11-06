#!/system/bin/busybox sh
# Physical-menu handler. Debug access requires deliberate provisioning first.
set -eu
CONF_FILE=/data/userdata/remote_access
CURRENT_MODE=$(cat "$CONF_FILE" 2>/dev/null || true)
case "$CURRENT_MODE" in 0|1|2|3|4) ;; *) CURRENT_MODE=0;; esac

debug_ready() {
    [ -f /data/userdata/cozy_debug_enable ] || return 1
    [ -f /data/userdata/passwd ] || return 1
    hash=$(awk -F: '$1=="root" { print $2; exit }' /data/userdata/passwd)
    case "$hash" in '$5$'*|'$6$'*) ;; *) return 1;; esac
    digest=$(printf '%s' "$hash" | sha256sum | cut -d ' ' -f 1)
    [ "$digest" != "$(cat /system/etc/cozy/upstream-root-hash.sha256)" ]
}
debug_ready || CURRENT_MODE=0
ipt() { xtables-multi iptables "$@"; }
apply() {
    # Guards cover rule replacement, including a native reconnect flush.
    for port in 23 5555; do
        ipt -C INPUT -p tcp --dport "$port" -j REJECT 2>/dev/null || \
            ipt -I INPUT 1 -p tcp --dport "$port" -j REJECT || return 1
    done
    ipt -N COZY_DEBUG 2>/dev/null || true
    ipt -F COZY_DEBUG || return 1
    if [ "$CURRENT_MODE" = 1 ] || [ "$CURRENT_MODE" = 2 ] || [ "$CURRENT_MODE" = 3 ]; then
        ipt -A COZY_DEBUG -i br0 -p tcp --dport 23 -j ACCEPT || return 1
    fi
    if [ "$CURRENT_MODE" = 2 ] || [ "$CURRENT_MODE" = 3 ]; then
        ipt -A COZY_DEBUG -i br0 -p tcp --dport 5555 -j ACCEPT || return 1
    fi
    ipt -A COZY_DEBUG -j REJECT || return 1
    for port in 23 5555; do
        while ipt -C INPUT -p tcp --dport "$port" -j COZY_DEBUG 2>/dev/null; do
            ipt -D INPUT -p tcp --dport "$port" -j COZY_DEBUG || return 1
        done
        ipt -I INPUT 1 -p tcp --dport "$port" -j COZY_DEBUG || return 1
        while ipt -C INPUT -p tcp --dport "$port" -j REJECT 2>/dev/null; do
            ipt -D INPUT -p tcp --dport "$port" -j REJECT || return 1
        done
    done
    if [ "$CURRENT_MODE" = 0 ] || [ "$CURRENT_MODE" = 4 ]; then
        pkill telnetd 2>/dev/null || true
        pkill adbd 2>/dev/null || true
    else
        [ -f /data/userdata/telnet_disable ] || pidof telnetd >/dev/null || telnetd -l login -b 0.0.0.0
        if [ "$CURRENT_MODE" = 2 ] || [ "$CURRENT_MODE" = 3 ]; then
            [ -f /data/userdata/adb_disable ] || pidof adbd >/dev/null || adb
        else
            pkill adbd 2>/dev/null || true
        fi
    fi
    # Keep the existing advanced web-off modes, with no duplicate rules.
    for family in iptables ip6tables; do
        if [ "$CURRENT_MODE" = 3 ] || [ "$CURRENT_MODE" = 4 ]; then
            xtables-multi "$family" -C SERVICE_INPUT -p tcp --dport 80 -j REJECT 2>/dev/null || \
                xtables-multi "$family" -I SERVICE_INPUT -p tcp --dport 80 -j REJECT || return 1
        else
            while xtables-multi "$family" -C SERVICE_INPUT -p tcp --dport 80 -j REJECT 2>/dev/null; do
                xtables-multi "$family" -D SERVICE_INPUT -p tcp --dport 80 -j REJECT || return 1
            done
        fi
    done
}
case "${1:-get}" in
    get) exit "$CURRENT_MODE";;
    set_next)
        debug_ready || { echo 'Debug access needs explicit provisioning and a unique root password' >&2; exit 1; }
        CURRENT_MODE=$(((CURRENT_MODE+1)%5))
        ;;
    boot) ;;
    *) exit 2;;
esac
if ! apply; then
    pkill telnetd 2>/dev/null || true
    pkill adbd 2>/dev/null || true
    exit 1
fi
old=$(cat "$CONF_FILE" 2>/dev/null || true)
[ "$old" = "$CURRENT_MODE" ] || printf '%s\n' "$CURRENT_MODE" > "$CONF_FILE"
