# 0011: Dual boot: install alongside Windows, and never erase another OS without asking

- Status: proposed, 2026-11-23. Harsh asked to make GraceOS "compatible and safe for booting outside of VM, as in a dual boot setup". Claude designed and built it.
- Task: T-027. Builds on ADR 0005 (graceinstall is archinstall with GraceOS defaults).

## Context
Until now GraceOS was only installed onto blank virtual disks. archinstall 4.5 (what `graceinstall` runs), read for this:
- Its "best-effort default layout" wipes the whole chosen disk. Its manual partitioning can keep partitions, but marking the Windows ESP for formatting is one menu item away.
- Its default UEFI bootloader is systemd-boot, which needs the kernels on the ESP; a Windows ESP is usually 100 MiB. `bootctl install` always overwrites the ESP's fallback loader `EFI/BOOT/BOOTX64.EFI` (systemd `bootctl-install.c`, `force=true` on install), which on a Windows PC is Windows Boot Manager's copy. GRUB's default in archinstall is "removable", which writes the same file.
- GRUB doesn't list Windows unless os-prober is installed and `GRUB_DISABLE_OS_PROBER=false`.
- No GPU drivers unless a desktop *profile* is chosen (GraceOS uses none).
- Found while testing: if `lsblk` reports no partition-table type (udev not ready), archinstall starts from an empty table and writes it, deleting every partition, even with "keep existing data".

## Decision
- **A read-only scan first** (`installer/dualboot.py`): `lsblk` + `sfdisk --json` + `blkid -p`. ESPs and NTFS are mounted read-only to find Windows Boot Manager, `Windows/System32`, and `hiberfil.sys` (hibernated if it starts with `hibr`, the check ntfs-3g uses). The live USB is skipped.
- **Install alongside** is a generated archinstall `manual_partitioning` config, so archinstall still does all the partitioning (ADR 0005): every existing partition untouched, the existing ESP as `existing` (never formatted) at `/efi`, one new ext4 root in the chosen free region. **GRUB, not removable**: kernels stay on the root partition, and EFI/BOOT is left alone. The user reviews it in archinstall's menu.
- **Erase guard:** `graceinstall` wraps archinstall's `FilesystemHandler.perform_filesystem_operations`, the one step that writes to disks. Before it runs, the plan is compared with the scan: a wipe of a disk that holds an OS or data, or a `modify`/`delete` of such a partition, needs the device name typed (`--allow-erase` unattended). It also stops if archinstall's view of a disk (table type and partitions) differs from `sfdisk`'s. If archinstall's objects change shape, the guard refuses instead of guessing.
- **After the install,** an archinstall plugin (`on_genfstab`, the last hook, with the system still mounted): os-prober plus a first-boot rescan for GRUB; a basic-graphics (`nomodeset`) recovery entry (GRUB's own `GRUB_DISABLE_RECOVERY=false` + `GRUB_CMDLINE_LINUX_RECOVERY`), or a "safe graphics" systemd-boot entry; and the original `EFI/BOOT/BOOTX64.EFI` put back, but only if the firmware got a new boot entry for GraceOS.
- **Clock:** ask (UTC + a registry command for Windows, recommended; or local time via `/etc/adjtime`). The installer can't safely edit the Windows registry.
- **GPU:** packages from the PCI IDs, using the same package names as archinstall's own graphics-driver menu (`nvidia-open` for Turing and newer, i.e. device ID ≥ 0x1E00). Not on the live ISO: it must stay under 2 GiB.
- **Secure Boot:** guidance only (`docs/dual-boot.md`). No signed shim: `shim-signed` is AUR-only, and GraceOS would need its own signing key and process.

## Alternatives considered
- **systemd-boot with a new XBOOTLDR partition** for the kernels: keeps one bootloader for every install, but needs a second boot-type partition. In archinstall the "boot" flag on GPT means ESP, so it risks a second ESP on the Windows disk, which Windows tools handle badly. Possible later.
- **Partitioning ourselves** (sgdisk) for the alongside case: rejected by ADR 0005; archinstall's config interface does it.
- **Resizing NTFS from the installer:** rejected. Windows' own Shrink Volume is safer and handles its unmovable files.
- **Calamares** (graphical, has "install alongside"): heavy, still the option for a later graphical installer.

## Consequences
- The guard and the plugin depend on archinstall internals (`FilesystemHandler`, its disk-config objects, `plugins`). `build/dualboot-disk-test.py` exercises them against archinstall's real code on a loop device; run it after archinstall updates.
- Two bootloader paths: GRUB for dual boot, systemd-boot for blank disks.
- Real hardware is still the real test: firmware NVRAM quirks, NVIDIA, BitLocker prompts.
