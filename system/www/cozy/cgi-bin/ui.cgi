#!/system/bin/busybox sh
printf 'Content-Type: text/html; charset=utf-8\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nX-Frame-Options: DENY\r\nContent-Security-Policy: default-src '\''self'\''; script-src '\''self'\''; style-src '\''self'\''; img-src '\''self'\'' data:; connect-src '\''self'\''; base-uri '\''none'\''; frame-ancestors '\''none'\''; form-action '\''none'\''\r\n\r\n'
cat /system/etc/cozy/ui.html
