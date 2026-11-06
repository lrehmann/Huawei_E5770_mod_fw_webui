# Build and verify the complete experimental images

## Rebuild from this repository alone

The checked-in `firmware/experimental/` BIN files provide the immutable kernel,
bootloader, modem and other vendor payloads. Every writable-source filesystem
is reconstructed from `app/`, `system/` and `web/`, using the preserved base
permissions/ownership and explicit empty directories in
`firmware/base-layout.json`. No local Downloads files or network access are
required for this path.

Use Python 3.11+; Node.js and ShellCheck are needed for the broader code checks.
On Debian/Ubuntu, `python3`, `nodejs` and `shellcheck` provide these commands.

```sh
git clone https://github.com/lrehmann/Huawei_E5770_mod_fw_webui.git
cd Huawei_E5770_mod_fw_webui
python3 tools/build_firmware.py --check
python3 tools/check.py
python3 tools/build_firmware.py --experimental --output build/complete-firmware
```

The final directory contains the full 10-partition firmware BIN, full
3-partition WebUI BIN, `MANIFEST.json` and `SHA256SUMS`. The builder verifies every
base component and CRC before use, refuses missing base files unless an explicit
deletion has been reviewed, and preserves the vendor mount points omitted by
Git's empty-directory handling. Rebuilt filesystem partitions have canonical
timestamps, inode order, padding and symlink modes. Existing vendor modes and
UID/GID are retained; new Cozy files are root-owned.

The firmware transport prefixes and embedded upstream signature metadata are
retained for compatibility with the same modified/service-firmware workflow.
The modified images do not receive a new OEM signature. Offline structural
verification is separate from hardware compatibility and signature acceptance.

To opt into booting the experimental customization service in the resulting
main image:

```sh
python3 tools/build_firmware.py --experimental --enable-admin --output build/complete-personalization
python3 tools/build_firmware.py --check --template-dir build/complete-personalization
```

That main image has `ADMIN_FW.BIN` in its filename. The WebUI is byte-identical
to the standard set. Only the read-only `etc/cozy/admin-enabled` marker is added;
native-session verification and LAN filtering still apply. A persistent
`/data/userdata/cozy_admin_disable` flag overrides it. Telnet, ADB and kernel/NV
research patches stay off. Do not put this marker into the source tree; use the
explicit build option so manifests and checks reflect the choice.

`SOURCE_DATE_EPOCH` can override the archive epoch. The default is recorded in
`system/etc/cozy/build-epoch`. Changing it changes image hashes. The checks
validate actual packaged paths, content, ownership and modes against source,
not just an outer checksum.

## Bootstrap from the pinned upstream release

This path independently recovers the original base input images. It requires
HTTPS plus libarchive's `bsdtar` or 7-Zip to extract the upstream `.7z` archive.
On Debian/Ubuntu, install `libarchive-tools`; macOS's built-in `tar` is based on
libarchive. Download/extraction integrity is pinned in `firmware/base-download.json`.

```sh
python3 tools/fetch_base.py
python3 tools/build_firmware.py --experimental --base-dir .cache/releases/unpacked --output build/from-original-base
```

An already downloaded upstream archive can be supplied with
`python3 tools/fetch_base.py --archive /path/to/upstream.7z`. Its pinned digest is
still required. Only the two expected image members are extracted, and both
digests are checked. The user-supplied `21.327` stock image is not a base input
for this build.

## Other artifacts

```sh
./build.sh --experimental
```

This produces canonical standalone filesystem CPIO intermediates in
`build/experimental/`, with the same restored directories and vendor metadata.
They are useful for inspection; install the complete BIN pair described in
[INSTALL.md](INSTALL.md).

To create a distributable ZIP with both images, checksums, manifest, notices and
installation/recovery/build instructions:

```sh
python3 tools/package_release.py --bundle-dir firmware/experimental --output build/releases
python3 tools/package_release.py --bundle-dir build/complete-personalization --output build/releases
```

Publishing a new version requires updating `firmware/VERSION`, regenerating
both images and the checked-in manifests, running offline/source checks and
CI, and clearly retaining the hardware-validation status. The firmware is still
experimental until the device/recovery gates in the audit are actually tested.
