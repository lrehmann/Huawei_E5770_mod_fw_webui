# Backup and recovery for the experimental E5770 build

Read [INSTALL.md](INSTALL.md) first. Button-entry download mode and host USB
enumeration have been checked on the attached hotspot. No recovery loader,
firmware transfer or restore has been performed. A complete firmware package is
not a backup of a specific unit's NV, calibration, identity, bad-block state or
current configuration.

The current [preflash checkpoint](PREFLASH.md) records verified private settings
snapshots, pinned E5770 loader candidates and the remaining raw-backup/recovery
gates. An offline erase-suppression patch check is not a successful recovery boot.

The current owner selected a closed case and factory-provided update paths only.
Stock debug-interface checks did not yield a privileged console or readable NV
records. No full NAND/NV backup or proven recovery boot was obtained. Do not
infer recovery readiness from the verified settings/installer-CD copies, or use
the candidate loaders to work around the current installation scope.

## Observed download-mode entry

The [upstream E5770 release instructions](https://github.com/Huawei-LTE-routers-mods/Huawei_E5770_mod_fw_webui/releases/tag/v2.3.2)
describe entering download mode with the device off: hold the labeled Reset
button, press Power, then release the buttons as it starts. The owner performed
this sequence and observed the download/update screen. Use the labeled button,
not an unidentified circuit-board pad; holding Reset alone while running can
reset settings.

On this unit, the settled identity was Huawei `12d1:1442`, with a vendor
interface plus installer mass storage. WSL USB forwarding created `/dev/ttyUSB0`;
no serial port was opened and no protocol or loader was sent. The corresponding
native Windows vendor interface lacks a driver (problem code 28). USB forwarding
was detached/unshared afterward and its temporary firewall allowance removed.

To leave this mode after an inspection, hold Power until off, then start with
Power only, without Reset. Confirm the normal status screen before continuing.
The owner completed this exit sequence; the normal screen and PC installer-mode
identity `12d1:1f01` returned, with USB forwarding detached/unshared.
This button-entry mode does not prove BootROM entry, raw backup capability,
signature acceptance or recovery after damage to the bootloader/partition table.

## Before writing firmware

Keep a private record of the device label/variant, hardware revision, current
firmware/WebUI, USB mode, serial-port identities and `/proc/mtd` partition map.
Retain the exact known-good software for that device and an independently
verified method to enter its download/recovery mode. Store device-specific
backups outside Git and outside the hotspot's limited internal storage.

For an existing modified device that already offers an authorized root ADB
connection, these are read-only discovery commands:

```sh
adb devices -l
adb shell id
adb shell cat /proc/mtd
```

Require the intended single device and `uid=0`. If the host/daemon supports
binary-clean `exec-out`, a single **identified** MTD partition can be streamed to
the host without creating a file on the router. Replace `N` with the index from
your own map and use a private destination:

```sh
mkdir -p "$HOME/private-e5770-backup"
chmod 700 "$HOME/private-e5770-backup"
adb exec-out cat /dev/mtdN > "$HOME/private-e5770-backup/partition-first.bin"
adb exec-out cat /dev/mtdN > "$HOME/private-e5770-backup/partition-second.bin"
cmp "$HOME/private-e5770-backup/partition-first.bin" "$HOME/private-e5770-backup/partition-second.bin"
```

Check both command exit statuses, compare the host byte length to the partition
size from `/proc/mtd`, and calculate SHA-256 for both files. A zero-byte or short
file is a failed backup. If `exec-out` is unsupported, **do not** substitute a
PTY-based `adb shell` binary dump; terminal conversion can corrupt it. Use the
device's documented service/backup tool instead. NAND read/ECC errors require
device-specific handling; a short read must not be accepted or forced.

Repeatable per-partition reads are useful evidence but do not prove an atomic
snapshot while services are writing. Obtain a consistent service/recovery-mode
backup for mutable NV/calibration data using a verified device-specific method.
These logical MTD reads do not include raw NAND OOB/ECC data. Programmer dumps
need the correct NAND format and tooling; the upstream
[Balong raw-dump tools](https://github.com/Huawei-LTE-routers-mods/balong-raw-dump-tools)
convert a programmer dump and are not a tool that reads the router over ADB.

For YAFFS partitions, a matching logical read alone is not a verified restorable
backup: OOB tags can be essential. Obtain the appropriate `nanddump` capture,
including OOB and bad-block/ECC information, with tool options verified for that
exact build. A live mutable partition also needs a consistency strategy. See
the [E5770 maintainer's warning](https://4pda.to/forum/index.php?showtopic=818849&st=540).

## If the native interface fails but download mode works

1. Preserve the flasher log and the exact image hashes. Avoid repeated partial
   writes, factory resets and speculative NV edits.
2. Reconfirm the device and download serial port. Use the known-good complete
   **matching** firmware/WebUI pair prepared before the change.
3. Inspect both files offline with `balong_flash -m` and verify their SHA-256.
   Follow the same two-image procedure in [INSTALL.md](INSTALL.md), using those
   recovery filenames. Do not use a CPIO intermediate as a firmware file.
4. If that restore is rejected or the download port is unstable, stop and use
   the verified service/recovery plan. The currently untested stock `21.318`
   transition is not solved by renaming or forcing a different image.

The pinned original `v2.3.2` pair can be recovered for comparison or an intentional
return to that mod with:

```sh
python3 tools/fetch_base.py
```

This restores the **upstream modified base**, not the device's original stock
firmware. It has the older debug/security defaults described in the audit.
Its suitability as a device recovery image must be established before flashing.
The supplied stock `21.327.01.00.1133` image has valid container CRCs but is a
different version from installed `21.318.01.00.00`; neither its OEM authenticity
nor its suitability as rollback has been validated here.

## If download mode is gone

BootROM recovery may require opening the unit, an exact E5770-compatible RAM
loader, and a device-specific test point. The pinned candidate in
[`recovery.lock.json`](../firmware/recovery.lock.json) matches the reference
partition table and erase-suppression patch, but is unsigned and has not been
loaded on this unit. The generic
[balong-usbdload](https://github.com/forth32/balong-usbdload) utility alone does
not establish those prerequisites. A loader for E3372/E5377 is not evidence of
E5770 compatibility. This project does not supply a verified E5770 loader/test
point or a hardware-tested unbrick sequence. Obtain that exact recovery resource
before the initial development flash; do not short an unidentified pad or use a
random loader near the battery circuitry.

A factory reset changes settings; it does not restore the old firmware. There
is no factory-reset button sequence in this repository that can undo arbitrary
bootloader, partition-table or calibration damage.
