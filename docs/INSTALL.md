# Install Cozy on a Huawei E5770

Version: `0.1.0-alpha.1`, based on firmware `21.329.01.00.00` and WebUI
`17.100.19.01.00` / upstream mod `v2.3.2`.

The repository contains a **complete experimental two-image flash set**. All 10
main firmware partitions and all 3 WebUI-package partitions are present. The
kernel, modem, bootloader, partition table, OEM metadata and ISO come from the
pinned upstream base. The `system`, `app` and `web` filesystems contain Cozy.

**This build has passed offline format, CRC, content and reproducibility checks;
it has not been flashed or hardware-qualified.** CRC/SHA checks do not create an
OEM signature, prove stock-firmware acceptance, or establish a recovery path.

## 1. Confirm the installation path

| Current state | Path |
| --- | --- |
| Compatible modified E5770 firmware | Follow the development-upgrade procedure below after private backups and a usable recovery path. This is the entry condition documented by upstream; Cozy itself remains hardware-untested. |
| Compatible E5770 technological/service firmware | The same upstream entry condition applies. Confirm the exact variant, loader, partition map and recovery before proceeding. |
| Stock `21.318.01.00.00` | Direct installation is **not verified**. Establish a model-specific, authorized stock-to-service/mod transition first. Entering download mode alone does not satisfy this prerequisite. |
| Supplied stock `21.327.01.00.1133` file | This is a different raw update image, not a backup of the installed `21.318` firmware or proof of an accepted transition. Do not select it as an automatic rollback. |
| Another model or an uncertain E5770 variant | Do not flash these images. Confirm the label/API identity and matching recovery resources first. |

The photos in the [repository](https://github.com/lrehmann/Huawei_E5770_mod_fw_webui)
are appearance references supplied by the user. A matching case is not a model,
variant, partition-map or firmware-compatibility check.

Record the exact model/variant, hardware revision, current firmware/WebUI,
partition sizes, SIM/APN configuration and existing USB composition. Have a
working Stock/RNDIS USB composition before upgrading; the legacy ECM kernel
memory patch is not enabled by default in Cozy. Use the existing mod's supported
USB menu to change composition if necessary, while its management/recovery path
is still available. Do not guess an NV value. Have a
data-capable USB cable, a stable powered USB connection and at least 50% battery
for this development procedure. Do not run a flash while the battery or charging
behavior is unreliable. Use a direct USB connection and preserve connectivity to
the device throughout both image writes.

## 2. Obtain and verify the complete set

Clone this repository, or download the versioned archive from
[Releases](https://github.com/lrehmann/Huawei_E5770_mod_fw_webui/releases).
The committed default images are in `firmware/experimental/`. A downloaded ZIP
has the same files at its top level.

| File | Contents |
| --- | --- |
| `Cozy_E5770_0.1.0-alpha.1_FW.BIN` | Full 10-partition firmware, including the matching kernel/modem/boot components and Cozy system/app |
| `Cozy_E5770_0.1.0-alpha.1_WEBUI.BIN` | Complete 3-partition WebUI package, including the Cozy menu and screens |
| `SHA256SUMS` | Expected SHA-256 for both images |
| `MANIFEST.json` | Per-partition hashes, source fingerprints, variant and validation status |

Use both files from one version. A CPIO file from `build/experimental/` is a
developer intermediate and is not a substitute for either BIN file.

For Linux, from the directory containing the images:

```sh
sha256sum -c SHA256SUMS
```

On macOS, the equivalent offline integrity command is:

```sh
shasum -a 256 -c SHA256SUMS
```

For a source checkout, this stronger check also compares every packaged
filesystem path, file byte, mode and owner against source and the base layout,
and verifies unchanged base partitions and all CRCs:

```sh
python3 tools/build_firmware.py --check
```

### Choosing the customization-service default

The **standard** set keeps the experimental customization companion disabled.
The native router interface and built-in Cozy screens are present.

The optional **personalization** archive contains
`Cozy_E5770_0.1.0-alpha.1_ADMIN_FW.BIN` plus the same WebUI image. It explicitly
opts into starting the native-session-authenticated companion on the private
LAN at port 8080. Its manifest says `admin_enabled_by_default: true`; the standard
set says `false`. It does not enable Telnet, ADB or NV/kernel-memory patches.
The old HTTP/crypto dependencies and native-session compatibility still need
hardware validation; use this variant only on a development network you trust.

You can build that option yourself; see [BUILD.md](BUILD.md). If a standard
upgrade is preferred and the old mod already provides a trusted root shell,
the following **optional pre-upgrade preparation** opts into the companion for
the next Cozy boot:

```sh
adb shell id
# Continue only if this reports uid=0 and the intended device is selected.
adb shell touch /data/userdata/cozy_admin_enable
adb shell rm -f /data/userdata/cozy_admin_disable
```

Those commands change an opt-in marker. They are not a way to obtain a root
shell on stock firmware. A previously created `cozy_admin_disable` marker also
overrides the personalization variant's boot default.

## 3. Keep private backups and establish recovery

Do this before entering the flash workflow. See [RECOVERY.md](RECOVERY.md).
Preserve the original device-specific NV/calibration/identity data and the
partition map, plus the corresponding known-good software and exact E5770
recovery resources. Keep private backups outside this repository.

A general firmware download is not a replacement for device-specific NV data.
Read-only backup commands require an existing authorized root/service path;
stock credentials or root access are not supplied by this project. If that path
or the recovery loader is missing, stop at offline verification.

## 4. Prepare the flasher

The procedure follows [upstream E5770 firmware instructions](https://github.com/Huawei-LTE-routers-mods/Huawei_E5770_mod_fw_webui/releases/tag/v2.3.2)
and [forth32/balongflash](https://github.com/forth32/balongflash). The flasher
revision used for offline inspection is pinned in `firmware/flasher.lock.json`:
`bf43faa4b5f60205a7950b8ecee5fe81a3226239`.

### Linux

From the Cozy source checkout:

```sh
sudo apt-get update
sudo apt-get install --no-install-recommends git build-essential zlib1g-dev python3
mkdir -p .cache
git clone https://github.com/forth32/balongflash.git .cache/balongflash
git -C .cache/balongflash checkout --detach bf43faa4b5f60205a7950b8ecee5fe81a3226239
make -C .cache/balongflash
COZY_FLASHER="$PWD/.cache/balongflash/balong_flash"
COZY_IMAGES="$PWD/firmware/experimental"
```

If `.cache/balongflash` already exists, verify its origin and check out the
pinned revision instead of cloning over it. For a downloaded release archive,
set `COZY_IMAGES` to that extracted directory. The `-m` commands only inspect
files and exit before opening a serial port:

```sh
"$COZY_FLASHER" -m "$COZY_IMAGES/Cozy_E5770_0.1.0-alpha.1_FW.BIN"
"$COZY_FLASHER" -m "$COZY_IMAGES/Cozy_E5770_0.1.0-alpha.1_WEBUI.BIN"
```

For the personalization archive, use its `ADMIN_FW.BIN` filename in place of the
standard firmware filename. Expect **10** main-image entries and **3** WebUI
entries. Stop on any CRC/format error; do not use `-f` to force a damaged image.

### Windows

Install a compatible Huawei Mobile Connect/serial driver from a trusted source
and confirm the download-mode device in Device Manager. Obtain `balong_flash.exe`
from the [pinned upstream tree](https://github.com/forth32/balongflash/tree/bf43faa4b5f60205a7950b8ecee5fe81a3226239/winbuild/Release).
Its expected SHA-256 is:

```text
f89abc07653a569b84bc1350d2731bc7fd3b201a66a35a8799d7d5d94d5f915b
```

In PowerShell, from the extracted image directory:

```powershell
Get-FileHash -Algorithm SHA256 .\balong_flash.exe
Get-FileHash -Algorithm SHA256 .\Cozy_E5770_0.1.0-alpha.1_FW.BIN
Get-FileHash -Algorithm SHA256 .\Cozy_E5770_0.1.0-alpha.1_WEBUI.BIN
.\balong_flash.exe -m .\Cozy_E5770_0.1.0-alpha.1_FW.BIN
.\balong_flash.exe -m .\Cozy_E5770_0.1.0-alpha.1_WEBUI.BIN
```

Match the image hashes to `SHA256SUMS`/`MANIFEST.json`. For personalization, check
and inspect its `ADMIN_FW.BIN` instead. Actual Windows flashing is untested here.

macOS can build and verify the files. Upstream documents Linux and Windows for
flashing. A Linux VM requires reliable USB passthrough across device
re-enumeration; it is not validated by this project.

## 5. Enter the existing compatible download mode

Only after steps 1–4 are satisfied, upstream documents either method:

1. Power the E5770 off. Hold its rear Reset button under the cover while pressing
   Power to enter firmware-download mode.
2. If an already available, authorized AT port exists, send `AT^GODLOAD` using a
   terminal. Changing USB composition to expose an AT port is a separate step;
   do not perform an unverified composition/NV change to get past a missing port.

Observe the new serial device. On Linux inspect `dmesg` and `/dev/serial/by-id/`;
resolve it to the correct short `/dev/ttyUSBn` path. On Windows record its actual
COM number in Device Manager. Do not use the modem's network adapter or guess a
COM port. A download-mode port does not prove that a stock signature check has
been bypassed.

## 6. Write both images — development hardware only

The following commands **write firmware**. The first uses upstream's `-k`
option to avoid an intermediate reboot, then the second writes the WebUI and
allows the normal final reboot. This sequence is derived from the flasher's
documented options; it has not been tested on a physical Cozy device.

Linux, using the actual serial port identified above:

```sh
COZY_PORT=/dev/ttyUSB0
# Replace this example with the confirmed download-mode port.
sudo "$COZY_FLASHER" -p "$COZY_PORT" -k "$COZY_IMAGES/Cozy_E5770_0.1.0-alpha.1_FW.BIN"
# Continue only after a successful first write and the expected download port remains available.
sudo "$COZY_FLASHER" -p "$COZY_PORT" "$COZY_IMAGES/Cozy_E5770_0.1.0-alpha.1_WEBUI.BIN"
```

Windows, replacing `7` with the confirmed COM number:

```powershell
.\balong_flash.exe -p 7 -k .\Cozy_E5770_0.1.0-alpha.1_FW.BIN
# Continue only after a successful first write.
.\balong_flash.exe -p 7 .\Cozy_E5770_0.1.0-alpha.1_WEBUI.BIN
```

For personalization, substitute its `ADMIN_FW.BIN` in the **first** write only.
Reconfirm the port if it disappears or re-enumerates. Stop on rejected headers,
signature/authentication errors, timeouts or an uncertain device identity; do
not force retry with altered signature/download-type options.

Upstream's final-reset guidance is to send `AT^RESET` through an available AT
port or perform two power-button reboots. Allow the initial boot/NV-restoration
work to finish before another restart. Do not factory-reset as a substitute for
the second image or for a failed firmware write.

## 7. Verify the result

Open the native router interface at its literal LAN IP, normally
`http://192.168.8.1/`. Check the model, firmware/WebUI versions, charging status,
USB, Ethernet, Wi-Fi, APN/SIM registration, DNS and cellular reconnect. The native
version strings remain the base Huawei versions; the Cozy version is in the
bundle manifest. Check the new startup/goodnight screens and normal screen
timeouts. Record failures rather than treating the first successful page load
as a stability or security test.

If the companion was explicitly enabled, sign in to the **native** interface at
that same IP, then use **System → Personalize your hotspot**. The companion is at
`http://192.168.8.1:8080/cgi-bin/ui.cgi` when that is the actual private `br0` IP.
Select a theme/message and save; screen changes apply at the next normal boot.
If native-session verification fails, it remains closed. Do not disable auth or
open the service to WAN to work around it.

Fresh root accounts are locked, and Telnet/ADB are not automatically started.
This firmware provides no default root password. Recovery relies on the
separately prepared download/service path, not a promised debug shell.
