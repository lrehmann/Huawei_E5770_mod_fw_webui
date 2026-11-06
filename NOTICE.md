# Component notices

This repository contains a mixture of original modifications, open-source
programs and proprietary Huawei firmware material inherited from
[Huawei-LTE-routers-mods/Huawei_E5770_mod_fw_webui](https://github.com/Huawei-LTE-routers-mods/Huawei_E5770_mod_fw_webui).
There is no blanket license covering those inherited components. Preserve
existing notices and observe the respective component licenses and any
redistribution requirements before publishing firmware binaries.

Huawei open-source notices remain under `app/config/*/config/device/` and
`app/config/device/`. The user-supplied Huawei source archive is not redistributed
here. Companion OLED source inspected for ABI context is available separately
under LGPLv3 at
[Huawei-LTE-routers-mods/huawei_oled_hijack](https://github.com/Huawei-LTE-routers-mods/huawei_oled_hijack);
its source and library were not newly rebuilt or relicensed by this milestone.

The updated CA certificate bundle is derived from Mozilla through
[curl's CA extraction service](https://curl.se/docs/caextract.html) and is licensed
under [MPL 2.0](https://www.mozilla.org/en-US/MPL/2.0/). Bundle provenance and the
original extraction header are retained. The bundle's SHA-256 is recorded in
`audit/provenance.json`.

The Balong inspection utility implements the documented container layout and
standard CRC16/X25 algorithm; layout reference:
[forth32/balongflash](https://github.com/forth32/balongflash).

New Cozy tools, frontend, tests, glyphs and artwork are source additions for this
fork. No ownership or relicensing claim is made over third-party material.
