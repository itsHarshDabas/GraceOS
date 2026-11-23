# Installing GraceOS next to Windows (dual boot)

`graceinstall` checks your disks before it changes anything and keeps Windows working. This page is what to do in Windows first, what the installer does, and how to fix the usual problems on real PCs.

## 1. In Windows, before you start
1. **Back up** anything you can't lose. Partitioning is where data gets lost; the installer is careful, but a backup is the only real safety net.
2. **BitLocker / Device Encryption.** If `C:` is encrypted, save the recovery key first (https://aka.ms/myrecoverykey, or `manage-bde -protectors -get C:` as administrator). A new boot loader, a changed boot order or a Secure Boot change can make Windows ask for it. Safest: **Settings > Privacy & security > Device encryption** (or Control Panel > BitLocker) **> Suspend protection** before you install, and resume it afterwards.
3. **Turn off Fast Startup**, then shut down fully. Fast Startup is really hibernation: Windows keeps `C:` "in use", and writing to it from Linux corrupts it. Control Panel > Power Options > *Choose what the power buttons do* > *Change settings that are currently unavailable* > untick **Turn on fast startup**. Or, as administrator: `powercfg /h off`. `graceinstall` reads `hiberfil.sys` and stops if Windows is still hibernated.
4. **Make free space.** Disk Management (`diskmgmt.msc`) > right-click `C:` > **Shrink Volume**. 40 GB or more for GraceOS (20 GB is the minimum). Leave the new space *unallocated*; don't format it.
5. **Clock (optional, recommended).** Windows keeps the PC's hardware clock in local time, Linux in UTC, so the time is off by your UTC offset after switching. Make Windows use UTC, as administrator:
   ```
   reg add "HKLM\System\CurrentControlSet\Control\TimeZoneInformation" /v RealTimeIsUniversal /d 1 /t REG_DWORD /f
   ```
   Or skip this and pick "local time" in `graceinstall` (it writes `LOCAL` to `/etc/adjtime`).

## 2. Firmware (BIOS/UEFI) settings
- **Boot the USB stick in UEFI mode** (its entry usually starts with "UEFI:"). Windows on any PC from the last ten years is a UEFI install, and a BIOS-mode GraceOS can't start it. `graceinstall` warns if you started in BIOS mode.
- **Secure Boot:** the GraceOS ISO isn't signed, so turn Secure Boot **off** to start it (and leave it off for the installed GraceOS; see [Secure Boot](#secure-boot)). Windows 10 and 11 keep working with it off. With BitLocker, Windows asks for the recovery key once after this change, which is why step 1.2 matters.
- If the normal menu entry gives a black or frozen screen (common with NVIDIA), pick **"GraceOS live medium …, safe graphics"**. It boots with `nomodeset` (basic graphics).

## 3. Running graceinstall
`graceinstall` scans first (read-only) and prints the disks, what is installed, and warnings: BitLocker, hibernated Windows, Secure Boot, BIOS mode. If it finds another OS it asks:
1. **Alongside it, in free space** (recommended). GraceOS gets one new ext4 partition in the free space you pick. The existing EFI system partition (ESP) is reused at `/efi`, *not formatted*. The boot loader is GRUB with os-prober, so the menu lists Windows. GRUB keeps the kernels on the GraceOS partition, so Windows' small (100 MB) ESP is enough. Nothing that exists is deleted or formatted.
2. **Partition it yourself** in archinstall's menu (advanced).
3. Quit.

Then it asks about the clock (UTC or local time), and opens the usual installer menu with everything filled in. Set your **Timezone** there.

**Safety net:** whatever you choose in the menu, right before any disk is touched `graceinstall` checks the plan. If it would wipe a disk or format/delete a partition that holds Windows, BitLocker, an ESP, a recovery partition or any filesystem with data, it lists them and stops unless you type the device name. Unattended (`--silent`) installs stop unless you pass `--allow-erase /dev/…` for it. It also stops if the installer has misread a disk's partition table, which would otherwise rewrite it.

**Graphics drivers** for the detected GPU are added to Full installs: Intel `vulkan-intel intel-media-driver`; AMD `vulkan-radeon`; NVIDIA Turing (GTX 16xx / RTX 20xx) and newer `nvidia-open nvidia-utils libva-nvidia-driver` with `nvidia_drm modeset=1`; older NVIDIA cards get the open `nouveau` driver (NVIDIA's current driver dropped them; the legacy one is AUR-only). Skip with `--no-gpu-detect`. CPU microcode (`intel-ucode`/`amd-ucode`) and `linux-firmware` come from archinstall on real hardware; `sof-firmware` (sound on most Intel laptops since 2019) is in every install.

## 4. After installing
The boot menu (GRUB) shows GraceOS, **"… (recovery mode)"** (basic graphics, `nomodeset`, with the fallback initramfs available under *Advanced options*), and **Windows Boot Manager**. With systemd-boot (a fresh disk with no Windows), there is a **"GraceOS …, safe graphics"** entry instead.

The ESP's fallback loader `EFI/BOOT/BOOTX64.EFI` belongs to Windows. GraceOS boots from its own firmware entry ("GRUB" or "Linux Boot Manager"), and `graceinstall` puts the original fallback back if the bootloader install replaced it. (It keeps GraceOS's copy only when the firmware refused to save a boot entry, since otherwise nothing would start GraceOS, and says so.)

### If something goes wrong
- **The PC boots straight into Windows.** Some firmware (often HP and some Lenovo models) always starts Windows Boot Manager. Open the firmware's boot menu (F12/F9/Esc at power-on) and pick GRUB, or move GRUB to the top of the boot order in the firmware settings. If the firmware resets it every boot, run as administrator in Windows: `bcdedit /set {bootmgr} path \EFI\GRUB\grubx64.efi` (undo with `bcdedit /set {bootmgr} path \EFI\Microsoft\Boot\bootmgfw.efi`).
- **Windows is missing from GRUB.** It is looked for again on the first boot. If it's still missing: `sudo grub-mkconfig -o /efi/grub/grub.cfg`. You can always start Windows from the firmware boot menu.
- **Black screen after the GRUB menu.** Pick the recovery mode entry (basic graphics). On NVIDIA, check `lsmod | grep nvidia` and the kernel log: `journalctl -b -1 -k`.
- **BitLocker recovery screen.** Enter the key from step 1.2; Windows starts normally afterwards. Then resume BitLocker if you suspended it.
- **Clock wrong in one of the two systems.** See step 1.5; pick one convention for both.

## Secure Boot
GraceOS doesn't ship a signed shim yet, so it runs with Secure Boot off. If you need Secure Boot on (some anti-cheat games or company policies on the Windows side):
- Use your own keys with `sbctl` (in Arch's `extra` repo), and **enroll Microsoft's keys too** (`sbctl enroll-keys --microsoft`), or Windows and many GPUs' firmware stop working. With GRUB, it has to be reinstalled for Secure Boot first (see the Arch wiki, *Unified Extensible Firmware Interface/Secure Boot*, "Using your own keys" and GRUB's `--disable-shim-lock`).
- This changes the firmware's key database, so BitLocker asks for its recovery key once.
- Not automated or tested by GraceOS yet.

## What has and hasn't been tested
See the pull request that added this page and `docs/PROJECT_STATUS.md`. In short: the disk logic is tested against a fake Windows disk (a loop device) with archinstall's real partitioning code, and unit-tested; nothing here has been run on a real PC yet.
