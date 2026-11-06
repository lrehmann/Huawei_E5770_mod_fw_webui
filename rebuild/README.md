# Remaining dependency and kernel work

The fork changes readable scripts, configuration, artwork and web code. Complete
experimental BIN packages now include the preserved base boot/kernel/modem
components. These assemblies do not modernize those old vendor binaries.

1. Rebuild a minimal companion HTTP stack and a compatible BusyBox from reviewed,
   pinned maintained sources. BusyBox's official site currently labels 1.36.1
   stable and 1.38.0 unstable; choose after advisory review, not just the larger
   version number. Preserve required applets and audit the change from legacy
   `timeout -t` to the newer command syntax. Validate both CGI environment and
   signal/exit behavior under ARM emulation before replacing the current binary.
   Apply `oled-bounds.patch` to pinned companion source commit
   `8ae8f06c226d972b78f2398ef2232fd7bd109969` during the OLED-library rebuild;
   its patch-application check passed, but no replacement library is shipped.
2. Build isolated optional curl/OpenSSL/OpenVPN/DNS dependencies with the device's
   ARM EABI and Linux 3.4 syscall constraints. Keep vendor Bionic and optional
   glibc ABIs separate. A current `libssl` is not a drop-in replacement for the
   existing Bionic `libssl.so` or optional `libssl.so.1.0.0`.
3. Inventory/close applicable dnsmasq, curl, OpenVPN, Wi-Fi and BusyBox advisories,
   including feature-dependent applicability and downstream backports. Record
   source commit, compiler, flags, license, SBOM, reproducible digest and emulator
   test results for each replacement.
4. Use the supplied `hi6921_v711_e5770s-923_defconfig` and drivers to establish an
   exact vendor-kernel baseline build before backporting fixes. The recovered
   21.329 kernel configuration disables stack protector, SECCOMP, read-only kernel
   text/data and Linux security modules, and enables several USB/debug surfaces.
   The candidate fragment here is a review input, not an applied kernel change.
5. Address strict DNS-over-TLS authentication with reliable clock bootstrap,
   individual device credentials, native HTTPS, signature-verification policy,
   and a tested stock recovery path.

The RAR's GCC 4.7 is a Linux-hosted ARM cross-toolchain and was not executed on
the macOS ARM host. No Linux build container/daemon was available in this
session. A source or version match does not establish ABI or hardware parity.

Primary references: [BusyBox](https://busybox.net/),
[OpenSSL support notice](https://mta.openssl.org/pipermail/openssl-announce/2019-December/000164.html),
[curl advisories](https://curl.se/docs/vuln-7.67.0.html),
[dnsmasq changes](https://thekelleys.org.uk/dnsmasq/CHANGELOG),
[active Linux releases](https://www.kernel.org/category/releases.html).
