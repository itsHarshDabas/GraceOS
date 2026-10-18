# GraceOS project status

_Last updated: 2026-10-18_

## Team
- **Harsh** (itsHarshDabas): base and ISO, AI platform, overall integration. Works with Claude Code, OpenCode and Cline.
- **Shell lead** (collaborator): Grace Shell (`desktop/`). Uses the same agents.
- Task ownership is tracked in [TASKS.md](TASKS.md).

## Phase 1: bootable ISO (in progress)

### Implemented
- `iso/`: a copy of the archiso `releng` profile (upstream commit 723da19), with:
  - the name changed to `graceos`, and GraceOS branding on the boot menus (UEFI systemd-boot, GRUB, syslinux), the MOTD and the hostname;
  - 15 official developer packages added to `packages.x86_64` (git, base-devel, python, uv, nodejs, ripgrep, btop and others);
  - the profile's symlinks recorded in `iso/symlinks.txt`, and recreated by `build/build-iso.sh`.
- `build/build-iso.sh`, `check-packages.sh` and `boot-test.sh`, plus `.github/workflows/build-iso.yml` (manual trigger only).

### Tested (2026-10-18, in an Arch live VM)
- `build/check-packages.sh`: **passed**. Every manifest package resolves in the official repos.
- First `build-iso.sh` run: packages installed into the image, and inside that root `git`, `python`, `node`, `uv`, `rg`, `btop` and `fastfetch` all resolved.
  - That run used an earlier symlink heuristic, which missed `etc/resolv.conf` and the masked `systemd-gpt-auto-generator`. I aborted it on purpose and replaced the heuristic with the manifest.
- **A second build with the manifest is running. As of this commit, no ISO has completed, and none has been boot-tested.**

### Not done or unverified
- `boot-test.sh` is unproven. The stock kernel command line has no `console=ttyS0`, so the serial grep probably never matches. QEMU in CI has no KVM, so the 300 s timeout may be too short. The OVMF path is unchecked. (T-002)
- The CI workflow has never run.
- No LICENSE yet; that's the owner's decision (T-009).

## Build environment (how Harsh builds on Windows)
- Host: Windows 11, 15.4 GB RAM. No WSL or docker. VirtualBox is unusable (the VBoxSDS service is disabled).
- **VMware Workstation 26** VM at `D:\GraceOS-vm\graceos-builder.vmx`: 8 GB RAM, 4 vCPUs, UEFI, NAT networking, a 40 GB scratch disk, and the official Arch ISO as its boot medium.
  - The .vmx needs explicit `pciBridge4-7` PCIe root ports, otherwise VMware reports "No PCIe slot available for Ethernet0".
- Workflow:
  1. Boot the live ISO and set a temporary root password from the console.
  2. SSH in from the host.
  3. `mkfs.ext4 /dev/sda` (the VM's scratch disk) and mount it at `/mnt/build`.
  4. `mount -o remount,size=3G /run/archiso/cowspace`.
  5. `pacman -Sy archiso`.
  6. Copy the repo over with tar and scp, then `WORK_DIR=/mnt/build/work bash build/build-iso.sh`.
- VMware Tools never reached the "running" state in the stock live ISO, so `vmrun runProgramInGuest` doesn't work. Use SSH.

## Next actions
1. Finish the build, then boot the output ISO in VMware (UEFI) and confirm: GraceOS boot menu, live shell, network, and dev tools present. (T-001)
2. Fix the boot test and enable CI on push. (T-002)
3. Write the Intelligence Layer architecture doc (T-004), and hand T-005, T-006 and T-007 to agents.
