# Cozy for Huawei E5770

A personal firmware fork with friendly pixel screens, a customization menu, and
the first security and stability repairs to the E5770 mod.

**Experimental source milestone. No device has been flashed. This is not a
security-audited release or a ready-to-flash firmware image.** The remaining
closed-source components and old kernel prevent that claim. Read
[the audit](docs/AUDIT.md) for the evidence, fixes, and open work.

Based on upstream commit `a4b7711f7564bfd408ce925564b128e05c20313d`, firmware
`21.329.01.00.00`, WebUI `17.100.19.01.00`, mod `v2.3.2`. The installed
`21.318.01.00.00` firmware needs a separately verified migration/recovery path.

## First changes

- Cat, cloud, and sprout screen artwork, with startup and goodnight screens.
- Custom welcome text, a companion name, display dim/sleep times, and status
  refresh settings, with live preview and profile import/export.
- A personalization link in the existing web-admin System menu.
- An experimental LAN companion that checks the native admin session for every
  request, rejects cross-site writes, and saves a bounded data-only profile.
- Debug services and kernel-memory research patches require explicit opt-ins.
  Fresh root accounts are locked; the upstream shared root password is rejected.
- Failed ad-block updates retain the last working list. Automatic HTTP
  download-and-execute Entware installation is disabled.
- Updated Mozilla CA roots, safer web authorization defaults, escaped device-info
  values, no unconditional backward clock reset, and no forced 15-minute idle TCP
  timeout or disabled connection-tracking checksums.
- Root-owned deterministic filesystem builds, SHA-256 manifests, ABI locks,
  regression checks, and GitHub Actions.

![Cozy settings preview](audit/ui-preview.jpg)

## Try the preview

Requires Python 3.11+ and Node.js for checks. No third-party Python packages are
needed for the firmware tools or tests.

```sh
python3 tools/preview.py
# http://127.0.0.1:18765/cgi-bin/ui.cgi?preview=1
```

The preview makes no device requests and cannot save to a hotspot. Exported
profiles contain preferences and screen bytes, with no session credentials.

```sh
python3 tools/check.py
./build.sh --experimental
```

Build results are in `build/experimental/`: three CPIO filesystem archives,
checksums, and a manifest. They have no Huawei update envelope, signature,
bootloader, kernel, modem, or recovery image. The tools never flash a device.
`SOURCE_DATE_EPOCH` can override the archive timestamps. Generated screen assets
can be refreshed with `python3 tools/generate_assets.py`.

## Device implementation

On a validated development device, the companion listens on the private `br0`
IPv4 address at port 8080. It stays **disabled by default** while native-session,
boot, and firewall compatibility remain untested. `cozy-admin enable` is the
explicit development opt-in; `cozy-admin disable` stops it and removes its boot
opt-in. Do not use the old BusyBox HTTP daemon on untrusted networks.

The user must already be signed in to the stock admin interface at the same
literal LAN IP. Native state `0`, the original session ID, a per-boot CSRF token,
an exact Host, and a matching Referer are required for writes. Authentication
failures do not fall back to an anonymous session.

Settings are committed together to `/data/userdata/cozy/profile`. Changes to
screen artwork and display timing are applied as RAM bind mounts before the
vendor OLED process starts on the next boot. Saving never restarts the modem or
rewrites a firmware partition. The companion name belongs to the customization
page; Wi-Fi SSID changes remain in the stock admin interface.

The source replaces every frame in `welcome`, `fast_power_up`, `fast_power_down`,
and `ani_power_off` in both display layouts. The offensive wording appears in
upstream's release description; it was not located as an actual startup string
in these filesystem trees. Verifying every physical startup path is still open.

## Supplied files and provenance

The supplied `.ZIP` is a raw, compressed Huawei update container for
`21.327.01.00.1133`; all 13 partition header/block CRCs passed. CRC validity does
not prove OEM authenticity or compatibility with the installed device.

The supplied RAR contains Linux 3.4.5 kernel source, the E5770s-923 board config,
Huawei drivers, and an older Linux-hosted ARM toolchain. It expands the available
source coverage; it is not a complete source tree for the proprietary modem or
all user-space binaries. Neither supplied archive is uploaded in this fork.

See [provenance](audit/provenance.json), [release checks](audit/release-containers.json),
[the implementation notes](docs/DEVELOPMENT.md), and
[the next rebuild work](rebuild/README.md).

Licenses are component-specific. See [NOTICE](NOTICE.md).
