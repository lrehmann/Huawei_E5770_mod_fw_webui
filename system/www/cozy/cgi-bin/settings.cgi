#!/system/bin/busybox sh
# A bounded settings API. Authentication is checked by Huawei on every request.
set -eu
umask 077
ulimit -f 64
PATH=/system/bin:/system/xbin:/bin:/sbin
BASE=/system/etc/cozy
RUN=/var/run/cozy-admin
STORE=/data/userdata/cozy
TMP=
staged=
cleanup() {
    [ -z "$staged" ] || rm -f "$staged"
    [ -z "$TMP" ] || rm -rf "$TMP"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
reply() {
    printf 'Status: %s\r\nContent-Type: application/json\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nContent-Security-Policy: default-src '\''none'\''; frame-ancestors '\''none'\''\r\n\r\n%s\n' "$1" "$2"
    exit 0
}
addr=$(cat "$RUN/bind-address" 2>/dev/null) || reply '503 Service Unavailable' '{"error":"Service is starting"}'
case "$addr" in ''|*[!0-9.]*) reply '503 Service Unavailable' '{"error":"Invalid service address"}';; esac
[ "${HTTP_HOST:-}" = "$addr:18080" ] || reply '403 Forbidden' '{"error":"Use the router LAN address"}'
case "${REQUEST_METHOD:-}" in GET|POST) ;; *) reply '405 Method Not Allowed' '{"error":"Method not allowed"}';; esac
cookie=${HTTP_COOKIE:-}
[ "${#cookie}" -le 512 ] || reply '401 Unauthorized' '{"error":"Sign in to the router first"}'
case "$cookie" in *SessionID=*) ;; *) reply '401 Unauthorized' '{"error":"Sign in to the router first"}';; esac
case "$cookie" in *[!a-zA-Z0-9_=\;\ .+/%-]*) reply '401 Unauthorized' '{"error":"Invalid session"}';; esac
TMP=$(mktemp -d "$RUN/request.XXXXXX") || reply '503 Service Unavailable' '{"error":"Try again"}'
# HiLink versions differ: some also require a request token for authenticated
# GETs. Fetch it for this exact session, and reject a replacement session.
session=$(printf '%s\n' "$cookie" | awk -F';' '{ for(i=1;i<=NF;i++) {v=$i; sub(/^ +/,"",v); if(v ~ /^SessionID=/) {n++; s=v} } } END {if(n==1) print s}')
[ -n "$session" ] || reply '401 Unauthorized' '{"error":"Invalid session"}'
if ! curl --silent --show-error --fail --noproxy '*' --connect-timeout 2 --max-time 4 \
    --max-filesize 16384 --cookie "$session" --output "$TMP/handshake" \
    "http://$addr/api/webserver/SesTokInfo"; then
    reply '503 Service Unavailable' '{"error":"Router authentication is unavailable"}'
fi
native_session=$(sed -n 's:.*<SesInfo>\([^<]*\)</SesInfo>.*:\1:p' "$TMP/handshake")
native_token=$(sed -n 's:.*<TokInfo>\([^<]*\)</TokInfo>.*:\1:p' "$TMP/handshake")
[ "$native_session" = "$session" ] || reply '401 Unauthorized' '{"error":"Sign in to the router first"}'
case "$native_token" in ''|*[!a-zA-Z0-9_+/=-]*) reply '503 Service Unavailable' '{"error":"Router authentication is unavailable"}';; esac
[ "${#native_token}" -le 256 ] || reply '503 Service Unavailable' '{"error":"Router authentication is unavailable"}'
# No redirects, proxies, URLs, paths, or commands come from the request.
if ! curl --silent --show-error --fail --noproxy '*' --connect-timeout 2 --max-time 4 \
    --max-filesize 16384 --cookie "$session" --header "__RequestVerificationToken: $native_token" \
    --output "$TMP/auth" "http://$addr/api/user/state-login"; then
    reply '503 Service Unavailable' '{"error":"Router authentication is unavailable"}'
fi
state=$(sed -n 's:.*<State>[[:space:]]*\([0-9][0-9]*\)[[:space:]]*</State>.*:\1:p' "$TMP/auth")
[ "$state" = 0 ] || reply '401 Unauthorized' '{"error":"Sign in to the router first"}'
token=$(cat "$RUN/csrf" 2>/dev/null) || reply '503 Service Unavailable' '{"error":"Service is starting"}'
[ "${#token}" = 64 ] || reply '503 Service Unavailable' '{"error":"Service is starting"}'
case "$token" in *[!0-9a-f]*) reply '503 Service Unavailable' '{"error":"Service is starting"}';; esac

if [ "$REQUEST_METHOD" = POST ]; then
    [ "${QUERY_STRING:-}" = '' ] || reply '400 Bad Request' '{"error":"Invalid request"}'
    case "${HTTP_REFERER:-}" in "http://$addr:18080/"*) ;; *) reply '403 Forbidden' '{"error":"Reload settings and try again"}';; esac
    [ "${CONTENT_TYPE:-}" = 'text/plain;charset=UTF-8' ] || \
        [ "${CONTENT_TYPE:-}" = 'text/plain' ] || reply '415 Unsupported Media Type' '{"error":"Expected a settings profile"}'
    length=${CONTENT_LENGTH:-0}
    case "$length" in ''|*[!0-9]*) reply '400 Bad Request' '{"error":"Invalid request length"}';; esac
    [ "${#length}" -le 4 ] && [ "$length" -ge 1 ] && [ "$length" -le 8192 ] || reply '413 Payload Too Large' '{"error":"Profile is too large"}'
    timeout -t 5 dd bs=1 count="$length" of="$TMP/request" 2>/dev/null || reply '400 Bad Request' '{"error":"Incomplete profile"}'
    [ "$(wc -c < "$TMP/request" | tr -d ' ')" = "$length" ] || reply '400 Bad Request' '{"error":"Incomplete profile"}'
    LC_ALL=C tr -cd '\012\040-\176' < "$TMP/request" | cmp -s "$TMP/request" - || reply '400 Bad Request' '{"error":"Invalid profile bytes"}'
    first=$(head -n 1 "$TMP/request")
    [ "$first" = "csrf=$token" ] || reply '403 Forbidden' '{"error":"Reload settings and try again"}'
    sed '1d' "$TMP/request" > "$TMP/profile"
    /system/bin/cozy-validate "$TMP/profile" || reply '400 Bad Request' '{"error":"Invalid settings profile"}'
    mkdir -p "$STORE"
    chmod 700 "$STORE"
    # A single rename commits all settings and screen bytes together.
    if ! cmp -s "$TMP/profile" "$STORE/profile"; then
        staged=$(mktemp "$STORE/.profile.XXXXXX") || reply '507 Insufficient Storage' '{"error":"Settings storage is full"}'
        if ! cat "$TMP/profile" > "$staged" || ! mv -f "$staged" "$STORE/profile"; then
            rm -f "$staged"
            reply '507 Insufficient Storage' '{"error":"Could not save settings"}'
        fi
    fi
    reply '200 OK' '{"saved":true,"screen_changes":"next_boot"}'
fi

if [ "${QUERY_STRING:-}" = status ]; then
    if ! curl --silent --show-error --fail --noproxy '*' --connect-timeout 2 --max-time 4 \
        --max-filesize 16384 --cookie "$session" --header "__RequestVerificationToken: $native_token" --output "$TMP/status" \
        "http://$addr/api/monitoring/status"; then
        reply '503 Service Unavailable' '{"error":"Status is unavailable"}'
    fi
    battery=$(sed -n 's:.*<BatteryPercent>\([0-9][0-9]*\)</BatteryPercent>.*:\1:p' "$TMP/status")
    case "$battery" in
        ''|*[!0-9]*) battery=null;;
        *) if [ "${#battery}" -le 3 ] && [ "$battery" -le 100 ]; then battery=$(printf '%s\n' "$battery" | awk '{printf "%d",$0+0}'); else battery=null; fi;;
    esac
    reply '200 OK' "{\"battery_percent\":$battery}"
fi
[ "${QUERY_STRING:-}" = '' ] || reply '400 Bad Request' '{"error":"Invalid request"}'
profile="$STORE/profile"
[ -f "$profile" ] && /system/bin/cozy-validate "$profile" || profile="$BASE/default.profile"
/system/bin/cozy-validate "$profile" || reply '503 Service Unavailable' '{"error":"Default settings are invalid"}'
printf 'Content-Type: application/json\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n\r\n'
awk -F= -v token="$token" '
    BEGIN { printf "{\"csrf\":\"%s\",\"settings\":{",token }
    { if (NR>1) printf ","; printf "\"%s\":\"%s\"",$1,substr($0,length($1)+2) }
    END { print "}}" }
' "$profile"
