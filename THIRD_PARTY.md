# Third-party components

## Exo 2

- Font source: https://github.com/google/fonts/tree/main/ofl/exo2
- Designer: Natanael Gama.
- License: SIL Open Font License 1.1, included in `www/fonts/OFL-Exo2.txt`.
- The regular and italic variable fonts are bundled locally in `www/fonts`; no CDN or online font request is required at runtime.

## LibreHardwareMonitor 0.9.6

- Source: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/tree/v0.9.6
- Official release: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/tag/v0.9.6
- License: Mozilla Public License 2.0 (MPL-2.0)
- Library binaries are distributed unmodified in `vendor/LibreHardwareMonitor`.
- Release checksum (LibreHardwareMonitor.zip): `086d9f1b5a99e643edc2cfaaac16051685b551e4c5ac0b32a57c58c0e529c001`.
- The release contains its upstream dependencies, governed by their respective licenses. See the upstream project and package metadata for source and license notices.
- MPL license: https://www.mozilla.org/en-US/MPL/2.0/

## Python / PyInstaller (portable executable only)

- Python: https://www.python.org/ · Python Software Foundation License.
- PyInstaller: https://pyinstaller.org/ · GPL with its bootloader exception permitting distribution of bundled applications.
- Source: https://github.com/pyinstaller/pyinstaller

## NVIDIA NVML

NVML is loaded from the computer's NVIDIA driver installation. No NVIDIA binaries are redistributed.

## PawnIO 2.1.0 (AMD64)

- Official unmodified, signed driver: https://github.com/namazso/PawnIO.Setup/releases/tag/2.1.0
- Driver SHA-256: `f92de04e5a02256e86ffa1b4252fe669282198b7329227f40e51bca9267d133d` (checked before loading).
- Source: https://github.com/namazso/PawnIO/tree/2.1.0, commit `e1043d7750f501b6b0d3ac0a71bd5b9406cd17b6`.
- GPL-2.0-or-later with the upstream device IO control interface exception. The upstream source archive, corresponding PawnPP submodule source, full GPL text and exception notice are bundled in `vendor/PawnIO/PawnIO-2.1.0-source.zip`, `PawnPP-source.zip`, `COPYING` and `LICENSE-and-source.md`. Extract the PawnPP source into the driver's `PawnPP` directory to reproduce the upstream source tree. See `manifest.json` for commits and checksums.
- WebOBS uses the legacy demand-load driver for a temporary UAC-authorized sensor session. It does not run the upstream installer, enable auto-start, or install a permanent user-mode service. Only its own temporary driver is stopped and removed on normal session exit; an existing accessible PawnIO driver is left under its original owner's control.
- The bundled driver is restricted to Windows 10 2004 (build 19041) or newer on AMD64. Older builds are rejected before loading because the upstream 2.2.0 release documents old Windows 10 compatibility fixes: https://github.com/namazso/PawnIO.Setup/releases/tag/2.2.0
