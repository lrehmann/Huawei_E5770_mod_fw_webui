# Development and device-validation notes

## Components

| Path | Responsibility |
| --- | --- |
| `system/www/cozy` | Dependency-free companion frontend and CGI endpoints |
| `system/etc/cozy` | ASCII profile validator, glyph-generated frames and XML patcher |
| `system/bin/cozy-validate` | Byte validation before line/schema parsing |
| `system/bin/cozy-apply` | Boot-time RAM overlays for screen artwork and timeouts |
| `system/bin/cozy-admin` | Opt-in private-LAN listener lifecycle and firewall |
| `tools/pixels.py`, `ui/glyphs.json` | Deterministic source artwork |
| `tools/balong.py`, `tools/inspect_inputs.py` | Read-only container/CRC/archive inspection |
| `tools/audit.py`, `audit` | Inventory, pinned hashes, provenance and audit evidence |
| `tools/build.py`, `tools/check.py`, `tests` | Archive building and offline regression checks |
| `tools/build_firmware.py`, `tools/firmware.py`, `firmware/base-layout.json` | Complete container assembly, immutable base checks, original owner/mountpoint metadata |

The native System menu opens a protected launcher; the companion then rechecks
the native login independently. It accepts a literal private IPv4 LAN address.
Host aliases intentionally require reopening the native admin at its LAN IP so
the browser sends the same SessionID cookie across ports. No wildcard binding,
HTTP redirect following, request-supplied upstream URLs, shell-evaluated
settings, or automatic runtime package installation is used.

The profile schema is exactly nine fields. `version` is `1`; theme is `cat`,
`cloud` or `sprout`; name is 1–16 restricted ASCII characters; message is 1–18
supported glyphs; dim is 1–60 seconds; sleep is at least dim and at most 300
seconds; refresh is 5, 10, 30 or 60 seconds. Screen payloads are exactly 1,024 and
2,048 bytes expressed as lowercase hex. POST bodies are at most 8,192 bytes.
Control bytes, extra/duplicate/missing fields and executable syntax are rejected.

All settings saves require a current native admin session, exact Host, matching
Referer, content type, and a 256-bit random per-boot CSRF token. Reads also require
the native session and Host. The old BusyBox server exports Referer to CGI but
does not expose an Origin environment variable; nonce validation remains the
primary cross-site-write defense. Native-session tests are mocked offline.

## Explicit research switches

These persistent markers are **not created** by the customization UI. The
optional personalization build instead places a read-only
`/system/etc/cozy/admin-enabled` marker in its system image. The default build
does not include that marker; `cozy_admin_disable` overrides both enable paths.

| File under `/data/userdata` | Effect |
| --- | --- |
| `cozy_admin_enable` | Start the experimental customization service at boot |
| `cozy_admin_disable` | Stop/keep the customization service disabled |
| `cozy_debug_enable` | Permit the physical debug menu after the unique root-password check |
| `cozy_nv_unlock_enable` | Permit the existing DATALOCK/NV kernel-memory bypasses |
| `cozy_usb_ecm_patch_enable` | Permit the exact-version ECM memory patch and ECM menu choice |
| `cozy_usb_mac_patch_enable` | Permit the existing exact-version USB MAC memory patch |

The debug hash check rejects the public upstream root-password seed and locked
accounts. It does not measure the strength of a user-chosen password. ADB is
still a privileged interface if deliberately opted in. The NV/ECM/MAC flags
should not be used with a different kernel version or a future read-only-text
hardening build.

## Required before a first device flash

1. Identify the precise E5770 variant, installed firmware, battery condition,
   USB mode and partition map. The supplied stock image is a different version
   and is not a device-specific backup.
2. Read and independently verify device-specific NV/calibration/identity and
   recoverable partition backups. Keep them private. Record checksums and test
   the actual recovery/bootloader path with compatible tooling and power.
3. Establish the complete stock-to-service/mod transition for 21.318.01.00.00.
   Match the 21.329 kernel/module/application ABI; never install only these
   application archives onto an unmatched kernel. Confirm the USB mode is usable
   without the gated ECM patch.
4. Rebuild/review the companion HTTP and crypto/networking dependencies. Preserve
   a recoverable management path while testing the stricter API allowlist,
   changed root policy and native auth/token/session behavior.
5. Boot an assembled recovery-capable test image and verify normal, fast-start,
   power-off, charge-only, low-battery, failure and recovery screens. Confirm no
   offensive overlay appears. Validate dim/sleep timing and profile fallback.
6. Verify USB, Ethernet, Wi-Fi AP/extender, DHCP/DNS, cellular reconnect, IPv4/IPv6
   filters, listener defaults and repeated firewall reconstruction. Include WAN,
   guest, expired-session, cross-site and malformed-input tests.
7. Compare idle/peak RAM, CPU, startup time, modem throughput/latency, USB
   stability, long-idle TCP sessions, charging behavior, temperature and battery
   endurance against a recorded stock baseline. Do not infer throughput gains
   from UI responsiveness.

None of these hardware/recovery gates has been completed in this source-only
milestone. The hotspot was inspected only through read-only API requests.

## Reproducing supplied-file inspection

```sh
python3 tools/inspect_inputs.py /path/to/E5770s_UPDATE_21.327.01.00.1133_WEBUI_17.100.17.01.1133_MRE5.ZIP \
  --source-archive /path/to/E5770s-923_open_src.rar
```

The filename extension is ignored by the Balong parser. RAR listing needs a
libarchive-capable `tar`. Inspection never runs scripts or binaries from an
archive. Source material and downloaded releases live in ignored `.cache/`;
source locks and non-sensitive evidence live in `audit/`.
