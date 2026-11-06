#!/system/bin/busybox sh

mkdir -p /bin /var /var/run /opt /tmp /online/opt
ln -s /system/bin/sh /bin/sh
ln -s /system/bin/busybox /bin/ash
ln -s /app/bin/oled_hijack/atc.sh /sbin/atc
# For Entware
mount --bind /online/opt /opt
# For TUN/TAP
mkdir -p /dev/net
[ -e /dev/net/tun ] || mknod /dev/net/tun c 10 200

# NV restore flag, load patches only when normal boot.
if [[ "$(cat /proc/dload_nark)" == "nv_restore_start" ]];
then
    /etc/huawei_process_start
    exit 0
fi

/etc/fix_ttl.sh 0
# Install display overlays before the vendor starts the OLED process.
/system/bin/cozy-apply || echo 'Cozy: display overlay unavailable; using built-in screens' >&2
/etc/huawei_process_start

# TUN/TAP support
insmod /system/bin/kmod/tun.ko
# EXT2/3/4
insmod /system/bin/kmod/crc16.ko
insmod /system/bin/kmod/mbcache.ko
insmod /system/bin/kmod/jbd2.ko
insmod /system/bin/kmod/ext4.ko

# Set time closer to a real time for time-sensitive software.
# Needed for everything TLS/HTTPS-related, like DNS over TLS stubby,
# to work before the time is synced over the internet.
BUILD_EPOCH=$(cat /system/etc/cozy/build-epoch)
case "$BUILD_EPOCH" in ''|*[!0-9]*) BUILD_EPOCH=0;; esac
NOW_EPOCH=$(date -u +%s)
[ "$NOW_EPOCH" -ge "$BUILD_EPOCH" ] || date -u -s "@$BUILD_EPOCH"

busybox sysctl -p /system/etc/sysctl.conf
# Research-only kernel memory patches are no longer automatic.
if [ -f /data/userdata/cozy_nv_unlock_enable ] || [ -f /data/userdata/cozy_usb_ecm_patch_enable ]; then
    /etc/patchblocked.sh boot
fi
[ ! -f /data/userdata/cozy_usb_mac_patch_enable ] || /etc/patch_usbmac.sh

# Remove /online/mobilelog/mlogcfg.cfg if /app/config/mlog/mlogcfg.cfg does NOT exist
# Disables mobile logger and saves flash rewrite cycles
[ ! -f /app/config/mlog/mlogcfg.cfg ] && rm /online/mobilelog/mlogcfg.cfg

[ ! -f /data/userdata/passwd ] && cp /system/usr/default_files/passwd_def /data/userdata/passwd
# Debug listeners are only started by remote_access.sh after its explicit
# opt-in, unique-password check, and LAN firewall have succeeded.

/app/bin/oled_hijack/autorun.sh
# Entware autorun
[ -f /data/userdata/entware_autorun ] && /opt/etc/init.d/rc.unslung start

# The experimental companion remains opt-in until device validation is complete.
if [ -f /data/userdata/cozy_admin_enable ] || [ -f /system/etc/cozy/admin-enabled ]; then
    /system/bin/cozy-admin start &
fi

# fix_ttl.sh 2, dns_over_tls.sh and anticenshorship.sh are called
# from /system/bin/iptables-fixttl-wrapper.sh by /app/bin/npdaemon.
