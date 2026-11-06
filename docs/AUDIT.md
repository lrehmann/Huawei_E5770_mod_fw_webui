# E5770 audit — experimental complete flash set

Reviewed on November 5, 2026 (America/Los_Angeles).

The source fork, complete flash-set assembly and a broad static inventory are
complete for this milestone.
**A complete firmware security audit is not complete.** Neither the proprietary
baseband/bootloader implementations nor all vendor daemons have corresponding
source here, and the new image has not been run on hardware. No stability,
security-certification, or radio-speed improvement is claimed from offline tests.

## Evidence and coverage

- Firmware base: upstream commit `a4b7711f7564bfd408ce925564b128e05c20313d`.
- Every regular file and symlink in `app`, `system`, and `web` is inventoried,
  with SHA-256 hashes for regular files. Gzip payloads are decompressed for text
  inspection. XML is parsed. ELF program headers and identifiable version
  strings are inspected. The exact current counts are in
  [inventory.json](../audit/inventory.json).
- The initial binary inventory contains 131 ELF objects: one declares an
  executable stack, 11 have no GNU stack header, 111 have a GNU RELRO segment,
  and 83 contain a stack-canary symbol. These are indicators, not proof of
  complete mitigation coverage, full RELRO, or exploitability.
- All three repository filesystem trees were compared against the packaged
  upstream release; comparable regular-file contents matched. The comparison
  does not certify all bootloader/kernel behavior.
- Header and per-block CRCs passed for the upstream firmware's 10 partitions,
  the upstream web package's 3 partitions, and the supplied stock image's 13
  partitions. No OEM digital-signature authenticity verification was performed.
- The supplied RAR has 9,475 outer members and a nested kernel archive with
  44,377 members. Its layout, board defconfig, kernel version, and selected
  configuration/build files were inspected. This is not a line-by-line audit of
  those 44,377 members. Its bundled build scripts and toolchain were not run.
- The upstream kernel was decompressed and its embedded configuration extracted
  into [upstream-kernel.config](../audit/upstream-kernel.config). It reports Linux
  3.4.5 built January 16, 2018. The supplied source's Makefile also reports 3.4.5.
  Matching the version alone does not prove an exact source-to-binary match.
- The local device was inspected through read-only API requests. No login,
  flash, reboot, remount, or device-setting write occurred.

Hashes and container evidence are in [provenance.json](../audit/provenance.json),
[release-containers.json](../audit/release-containers.json), and
[release-filesystem-comparison.json](../audit/release-filesystem-comparison.json).

## Findings and changes

| Priority | Finding | Current result / remaining work |
| --- | --- | --- |
| Critical | Linux 3.4.5 and proprietary baseband/boot components have no demonstrated current security-maintenance path. | Open. Vendor source helps driver review and backport assessment. A kernel replacement needs matching board drivers, modem interfaces, module ABI, and recovery tests. Linux 3.4 is absent from the [current upstream maintenance list](https://www.kernel.org/category/releases.html). |
| High | Firmware signature checks and sensitive NV restrictions were deliberately bypassed by upstream modifications. | Automatic DATALOCK/NV memory patches are now gated separately from the ECM patch. Hard-coded ECM and USB MAC memory writes require explicit flags. Firmware-signature verification in closed components is still not restored. |
| High | Startup launched Telnet/ADB, with a shared root-password seed and filtering applied later. | Removed automatic listener launches. Fresh root seed is locked. Debug provisioning needs an explicit flag and a changed SHA-256/SHA-512 crypt root hash, plus LAN-only filtering before listeners start. Firewall failure stops listeners. USB/recovery boot paths still need hardware observation. Opted-in ADB remains a privileged research interface. |
| High | OpenSSL 1.0.1e in vendor Bionic libraries; 1.0.2t in the optional glibc stack. | Open. [OpenSSL ended public 1.0.2 support in 2019](https://mta.openssl.org/pipermail/openssl-announce/2019-December/000164.html). Updating CA roots does not repair cryptographic-library vulnerabilities. Replacing these shared libraries without ABI work can break native daemons. |
| High | curl 7.67.0-DEV, OpenVPN 2.4.8, dnsmasq 2.80, BusyBox 1.29.3 and older vendor networking programs. | Open binary rebuild work. [curl's version-specific advisory list](https://curl.se/docs/vuln-7.67.0.html) and [dnsmasq's changelog](https://thekelleys.org.uk/dnsmasq/CHANGELOG) show later fixes. Each advisory still needs build-option/backport/reachability assessment; a version string alone does not prove the device is exploitable. |
| High | Entware fetched and executed an installer over HTTP; nested package fetches were also unauthenticated. | Network bootstrap removed. Existing installation status/shell and explicit autorun controls remain. Automatic broad recursive removal was also disabled. A reviewed, authenticated offline bootstrap is still needed. |
| High | Selected state-changing native API routes were allowed without login. | Removed nine reset, SD-card mutation, mobile-logger and update actions from the unauthenticated POST allowlist, and disabled the separate update whitelist. The closed native authorization implementation needs black-box tests on the matching firmware. Other stock guest routes remain for compatibility and need review. |
| High | DNS-over-TLS is configured with `GETDNS_AUTHENTICATION_NONE`. | Open. It is not authenticated DNS privacy. Strict TLS needs verified resolver identities, reliable boot-time clock initialization, and recovery from unavailable upstreams. No claim that updating the CA file alone fixes this setting. |
| High | Factory private TLS keys/certificates are shared across variants; native management uses HTTP. | Open. Per-device identity and an HTTPS migration are needed. Shared keys were not silently replaced with another shared key. The companion inherits the native HTTP-session transport risk. |
| Medium | Ad-block refresh could install an empty/partial list after a failed pipeline, and remove the old file before replacement. | Added an exclusive update lock, HTTPS-only redirects, TLS 1.2 minimum, transfer/time/size limits, hostname validation and entry-count limits. Only a validated list is renamed into place on the same filesystem, with a read-only-remount cleanup path. No automatic resolver restart. |
| Medium | Trust bundle dated from the old firmware era. | Updated to the November 5, 2026 Mozilla bundle from [curl's CA service](https://curl.se/docs/caextract.html). Verified the published SHA-256. This is provenance/integrity checking through HTTPS, not independent signing. Older OpenSSL compatibility remains a hardware test. |
| Medium | Clock reset unconditionally to December 2018; forced 900-second established TCP timeout; conntrack checksum checks disabled. | Clock only advances to a recorded build floor when behind it. Removed the forced 15-minute TCP timeout and checksum-disable write. Validate idle sessions, vendor offload behavior, clock sync and connectivity on hardware before release. |
| Medium | Device-info API values were concatenated into HTML. | Escaped values at that sink. Other legacy HTML sinks remain for review; this is not a completed WebUI XSS audit. |
| Medium | Wi-Fi password display was enabled by default. | Disabled that WebUI default. Existing NV settings and alternate screen paths may override it; verify actual behavior after a backed-up deployment. WPS configuration/reachability still needs separate assessment. |
| Medium | New customization service adds a privileged parser and an old BusyBox HTTP surface. | Implemented bounded ASCII-only data parsing, exact schema, no `eval`/`source`, per-request native-session verification, per-boot CSRF, Host/Referer checks, atomic profile writes, LAN binding/filtering and no CORS. It remains off by default. Replace or validate the HTTP implementation and native session semantics before enabling on hardware. |
| Medium | The connected stock unit already has a native HTTP redirect listener on the companion's original port 8080. | Alpha.2 moves the listener, firewall, authority checks and menu launcher to 18080. Regression checks reject native-port requests and keep Cozy firewall rules on the new port. Stock 18080 refused connections; compatibility on the new firmware remains a hardware test. |
| Medium | OLED hooks and ECM/MAC patches depend on exact binary addresses/ABI. | Added SHA-256 build locks for the critical unchanged application binaries. Skipped ECM menu selection without its opt-in. This does not validate every kernel-address assumption or make the installed 21.318 kernel compatible with the 21.329 application image. |
| High | A Git-only filesystem rebuild omitted empty `app/webroot` and `WebApp/common/autorun` directories and discarded vendor owner metadata. | Added a complete base layout and canonical filesystem recipe. Both CPIO and full-image builders now restore the empty directories, preserve vendor modes/UID/GID, and fail on missing base files without reviewed deletions. Regression tests check the mountpoint and ownership. |
| Medium | The separately available 128×64 OLED hook source has inclusive upper-bound checks on menu/script indices. | Prepared `rebuild/oled-bounds.patch` and verified it applies to the pinned source. It rejects invalid mapping indices and excludes the past-the-end script index. The binary library is unchanged; the fix needs a rebuild and ARM/hardware validation. |
| Low | Discriminatory wording appears in upstream release documentation; requested startup removal. | New fork text is respectful. Every frame in the known startup/shutdown animation entries was replaced with new artwork. The described slur was not found as an actual text startup asset in these matching filesystem trees. Two raw byte search hits were a blocklisted domain and ARM instruction bytes, not displayed messages. Physical startup, fast-start, charge-only and recovery paths are still unverified. |

## Customization implementation

Three independently rendered themes share the same reviewed 5×7 glyph table in
Python and JavaScript. Byte-for-byte tests compare both renderers at 128×64 and
128×128. Existing geometry, offsets, frame counts, priorities and timing metadata
are retained; charging, alarm and update-status animations are preserved.

The companion checks the original native session, fetches its HiLink request
token, requires native login state `0`, and rejects session replacement. This
fails closed if an older firmware binds sessions to an incompatible source IP
or has different token behavior. This compatibility must be tested, not worked
around by disabling authentication. Persistent profile files are mode 0600;
save commits all fields and screen data with one rename. Identical saves skip
the flash write. Screen overlays are applied on next boot from RAM, and the
save path never restarts services or remounts a firmware filesystem.

The preview mode is visibly marked, makes no device API calls, and cannot write
settings. Local browser checks covered all themes, both screen previews, text
editing and exported profile content. No console errors were observed.

## Validation and release status

`python3 tools/check.py` checks shell/JavaScript syntax, the automated security
regressions, all XML/gzip assets, and two complete deterministic CPIO builds.
Symlink permissions are normalized to 0777 so macOS and Linux produce the same
archive bytes; Git does not record host symlink permission bits.
The current count and archive hashes are in [verification.json](../audit/verification.json).
GitHub Actions runs the same offline command on Linux, including verification of
the committed complete images against all source filesystem bytes and metadata.

The complete two-image set retains the 10 main firmware partitions and 3
WebUI-package partitions from the pinned base. Only `system`, `app` and `web`
are replaced. Both prefixes, all other payload hashes and the base signature
metadata remain unchanged. All header/block CRCs are recalculated and verified.
The native upstream Balong flasher was compiled and used in offline `-m` mode;
it recognized both images and their 10/3 partition maps without CRC errors.
No serial port was opened. Details are in
[complete-firmware-validation.json](../audit/complete-firmware-validation.json).

The tests use isolated host fixtures and mocked native APIs/firewalls. They do
not demonstrate modem throughput, power stability, battery safety, a successful
boot, native-session compatibility, or recovery. Complete experimental BIN files
are published with their existing base transport/signature metadata; no new OEM
signature is created or authenticated. Direct installation from stock 21.318
remains unverified. The hardware gates are listed in
[DEVELOPMENT.md](DEVELOPMENT.md), with supported-path instructions in
[INSTALL.md](INSTALL.md).

The read-only [preflash checkpoint](PREFLASH.md) adds current device identity,
private configuration snapshots and static E5770 recovery-loader checks. No
raw NV/NAND backup, recovery boot or device firmware write has been completed.
