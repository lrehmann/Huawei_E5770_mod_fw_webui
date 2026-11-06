# Compatibility and backup checkpoint

Checked November 5, 2026, America/Los_Angeles. **The device is not cleared for
flashing.** No firmware, NV, USB-composition or power-state change was made.
Native admin authentication was used for read-only configuration snapshots.

## Confirmed on the connected unit

| Check | Result |
| --- | --- |
| Native device name | `E5770S` |
| Hardware | `CL2E5770SM` |
| Installed firmware | `21.318.01.00.00` |
| Installed WebUI | `17.100.14.01.00` |
| Purchase-record model supplied by the owner | White `E5770s-320`; physical label not independently read |
| USB on the Mac | Huawei `12d1:14db`, CDC ECM control and data interfaces; no Huawei serial or ADB interface exposed |
| USB on the work PC | Huawei `12d1:1f01`, installer mode; Linux descriptors confirm one mass-storage interface and no serial node |
| Management | Native HTTP server on 80; another native HTTP redirect listener on 8080 |
| Available shell paths | No ADB device; tested SSH, Telnet, alternate Telnet and TCP ADB ports refused connections |
| Battery during inspection | 18%, charging; capacity/health and sustained power behavior untested |

The previously selected Cozy port 8080 conflicts with an existing stock listener.
**Alpha.2 moves the companion, its firewall, Host/Referer checks and native menu
launcher to 18080**, which refused connections on this unit during inspection.
The standard image still keeps the companion disabled. A free port on stock
does not prove a successful boot or authentication on the new firmware.

## What was backed up and verified

Private host files contain 19 successful authenticated API/config responses,
including device identity, DHCP/DNS, Wi-Fi basic/security settings and MAC
filtering, APN profiles, connection policy, radio modes/bands, firewall, port
forwarding, DMZ, UPnP, SIP and feature/config metadata. Every successful response
was parsed as XML, read twice with identical bytes, and included in a SHA-256
manifest. Wi-Fi key fields were nonempty and did not appear masked; APN password
fields were empty in the responses. Values and individual snapshot hashes are
kept private. No passwords, session tokens, serial numbers, IMEI or configuration
exports are committed to Git.

These are **configuration snapshots for inspection/manual reconstruction**.
There is no tested automatic settings-import procedure. They are not full
firmware, NV/calibration, bad-block or NAND OOB backups. Native web-admin access
does not grant a Linux root shell or raw flash access.

The device's original installer CD-ROM was also read twice on the work PC:
5,515,264 bytes per read, with matching SHA-256. A Mac copy matched the two PC
reads. The private evidence/configuration archive was read back member by member
on the Mac, then copied to the PC and its full SHA-256 checked there. Both copies
are private; neither is stored in Git. An installer CD is not the radio firmware
or a raw NAND/NV backup.

## Recovery material staged offline

Pinned E5770 recovery material is recorded in
[`recovery.lock.json`](../firmware/recovery.lock.json). The private recovery kit
also contains the source snapshots, the original supplied stock comparison
image, and a host flasher verified in offline inspection mode. Nothing from the
kit has been sent to the hotspot.

The upstream `usblsafe-e5770.bin` candidate's embedded partition table is
byte-identical to the table in Cozy and the supplied `21.327` stock update:
20 partitions covering 128 MiB. The erase-suppression candidate differs from
`usbloader-e5770.bin` by exactly one ARM instruction at offset 4676, matching a
replay of upstream's V7R11 patch. Bad-block checking was not bypassed. This is
static evidence about a particular file, not proof that loading it cannot
write anything or that the unit will accept/boot it.

The [upstream signature inspector](https://github.com/Huawei-LTE-routers-mods/balong-signcheck)
reports no first-stage secuboot signature in the E5770 candidates. This is not
an OEM authenticity check and does not reveal the connected unit's fuse policy.
DDR/NAND compatibility, actual recovery entry and loader execution remain
unverified. The [upstream loader documentation](https://github.com/forth32/balong-usbdload)
explains why an ordinary loader can erase device-specific data; its `-c` erase
protection override and `-b` bad-block bypass are not part of this plan.

The supplied `21.327` image is a comparison input, not installed-version stock
rollback. The separately available o2 `21.200.19.01.405` downgrade archive also
targets a different starting version. Neither is an approved recovery image for
this unit. Matching reference partition tables do not establish the live map.

The base kernel's embedded `init.rc` mounts `system`, `app` and `webui` as JFFS2;
`userdata` and `online` use YAFFS2. CPIO update archive lengths are not the sizes
of the resulting compressed JFFS2 images. Live partition capacity, free space,
NAND geometry, bad blocks and image expansion still need checking.

## Host transport and remaining gates

This host is Apple Silicon and has libusb. Its current Huawei USB configuration
exposes Ethernet rather than the serial/root interface required for the dump.
A native flasher's successful `-m` run only checks an input file. It does not
validate a macOS USB driver or a recovery transport.

The owner supplied a direct USB connection to the Windows 11 work PC. Its
running WSL2 kernel meets the [Microsoft USB/IP requirements](https://learn.microsoft.com/en-us/windows/wsl/connect-usb).
The official usbipd-win 5.3.0 MSI passed its published SHA-256 and Windows
Authenticode check. It was installed with restart suppressed; the installer
returned success without requiring or performing a reboot. The new broad
inbound allow rule was disabled, and a staging inbound-deny rule is enabled.

A temporary rule scoped to the WSL guest allowed a normal-mode passthrough test.
Linux read the Huawei USB descriptors, finding only the installer mass-storage
interface. No code was loaded into the device. WSL IPv4 routes were unchanged.
The device was detached/unshared afterward, its original installer CD was
visible in Windows again, and the temporary allow rule was removed. Normal USB
forwarding is tested; forwarding in download/BootROM modes is not.

The pinned RAM uploader was built in an isolated user directory in WSL and
parsed the loader's 20-partition map in offline mode. Existing WSL services and
packages were not changed or restarted. No recovery loader was executed on the
hotspot. The USB/IP service remains guarded until another explicit inspection.

The Mac has UTM 4.5.3 on macOS 26.3, but no new recovery VM was created. The
direct PC route avoids needing to qualify Mac VM passthrough first.

The remaining requirements are:

1. Confirm the physical variant/board and obtain the live `/proc/mtd`, mount
   table, NAND geometry and USB NV/composition details through a trusted read
   interface. Do not obtain that interface by first overwriting stock firmware.
2. Obtain and independently reread device-specific NV/calibration and immutable
   flash partitions with expected lengths and matching hashes. Capture mutable
   data consistently. YAFFS/NAND restoration may require OOB/ECC and bad-block
   metadata; plain `cat` or `mtdblock` copies alone are insufficient.
3. Establish compatible installed-version recovery software and a verified
   device-specific recovery-entry method. Prove a non-erasing recovery boot and
   its host USB transport, ideally on a spare matching unit.
4. Verify the stock-to-service/mod transition from `21.318.01.00.00`, sustained
   power/battery condition, filesystem capacity and a usable management path
   with Cozy's ECM research patch disabled.

No raw NAND dump or hardware recovery success is claimed at this checkpoint.
