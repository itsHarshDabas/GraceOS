# GraceOS project status

_Last updated: 2026-10-19_

## Team
- **Harsh** (itsHarshDabas): base and ISO, AI platform, overall integration. Works with Claude Code, OpenCode and Cline.
- **Shell lead** (collaborator): Grace Shell. A v0 was built at Harsh's request in the `grace-candyland` repo (ADR 0004) for the Shell lead to review. Uses the same agents.
- Task ownership is tracked in [TASKS.md](TASKS.md).

## Phase 1: bootable ISO (in progress)

### Implemented
- `iso/`: a copy of the archiso `releng` profile (upstream commit 723da19), with:
  - the name changed to `graceos`, and GraceOS branding on the boot menus (UEFI systemd-boot, GRUB, syslinux), the MOTD and the hostname;
  - 15 official developer packages added to `packages.x86_64` (git, base-devel, python, uv, nodejs, ripgrep, btop and others);
  - the profile's symlinks recorded in `iso/symlinks.txt`, and recreated by `build/build-iso.sh`.
- `build/build-iso.sh`, `check-packages.sh`, `verify-iso.sh` (content checks) and `boot-test.sh` (QEMU boot, waits for the sshd banner).
- `.github/workflows/build-iso.yml`: runs check, build, verify and both boots on pushes to `main` and on PRs touching `iso/`, `build/` or the workflow.

### Tested (2026-10-18)

**Build** (in the Arch live VM):
- `build/check-packages.sh` **passed**: every manifest package resolves in the official repos.
- `build/build-iso.sh` **succeeded**, producing `graceos-2026.10.18-x86_64.iso`:
  - 1.7 GB, sha256 `dfe15fa918e13303a479e6cc35e090cd90ca01a34523942df80c5d42a3003226`;
  - `sha256sum -c` passes both in the VM and on the host;
  - no `ERROR` or `Failed to read` lines in the build log.

**ISO contents** (checked by mounting the ISO and its `airootfs.sfs`):
- Volume label `GRACEOS_202610`.
- Every UEFI and BIOS boot menu entry reads "GraceOS live medium".
- `/etc/hostname` is `graceos`, and the GraceOS MOTD is present.
- `resolv.conf`, `localtime`, the masked `systemd-gpt-auto-generator` and the `*.wants` links are real symlinks.
- `git`, `python`, `node`, `npm`, `uv`, `rg`, `fd`, `jq`, `btop`, `fastfetch`, `tmux`, `makepkg` and `lspci` are present.

**Boot** (VMware Workstation 26, ISO only, no disk, 3 GB RAM):

| Firmware | Result |
|---|---|
| UEFI | Booted to multi-user in about 40 s. DHCP lease with `client-hostname "graceos"`; sshd answers ("Permission denied" for root, which has no password). |
| BIOS | Booted. DHCP lease with `client-hostname "graceos"`; sshd answers the same way. |

**Automated checks** (2026-10-19, run inside the builder VM; QEMU 11.1.2 without KVM, i.e. TCG):
- `verify-iso.sh`: all 55 checks passed. On the stock Arch ISO it correctly fails the branding, hostname and tool checks.
- `boot-test.sh` BIOS: **PASS**, sshd banner after 85 s.
- `boot-test.sh` UEFI (OVMF 4m): **PASS**, sshd banner after 80 s.
- Negative test: a random-bytes "ISO" gives FAIL with rc=1, and no QEMU process is left behind.

### Not done or unverified
- **Interactive console not observed**: the tty1 autologin shell, the MOTD on screen, and running the tools on the booted system. Boot was verified only through DHCP, the hostname and sshd.
- Only VMware has been tested; no real hardware yet.
- The CI workflow has not run on GitHub yet. Runner disk space and KVM availability are unconfirmed; the boot test falls back to TCG.
- No LICENSE yet; that's the owner's decision (T-009).

## Phase 2: desktop, Grace Candyland (in progress, branch `shell/candyland`)

### Implemented
- Repo `itsHarshDabas/grace-candyland` (private for now, T-014): Hyprland config plus a Quickshell shell with the top bar, control center, Ask Grace launcher, dock, notifications, agent approvals (`grace-approve`) and Settings → Appearance. It has `make install` and an Arch PKGBUILD.
- The ISO installs it from the commit in `iso/candyland.ref`.
- The `grace` live user autologins on tty1 and starts the desktop.
- NetworkManager and BlueZ replace systemd-networkd and iwd.

### Tested (2026-10-19)
- **Shell in a real Hyprland 0.56.2 session** (builder VM, software rendering because VMware 3D is off): every module checked with screenshots, `tests/approve.sh` passes (allow → 0, deny → 1, no shell → 2), and `make check` (shellcheck plus `Hyprland --verify-config`) passes.
- **ISO** `graceos-2026.10.18-x86_64.iso`, 2.1 GB (1.7 GB before the desktop): `verify-iso.sh` ALL CHECKS PASSED, including the desktop, the live user and autologin.
- **Boot test (BIOS)**: PASS, sshd answered after 106 s. This shows networking comes up under NetworkManager.

### Not done or unverified
- **The live session reaching the desktop has not been observed.** `build/desktop-test.sh` (QEMU screenshot) failed on its first run because the builder's QEMU lacks `virtio-vga`. It now uses `-vga std`, but it hasn't been rerun: the builder VM lost its state after a low-memory power-off.
- **UEFI boot test**: not run for this ISO.
- **CI can't clone the private candyland repo** (T-014).

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
- **Gotchas that cost real time:**
  - Run remote commands through Git Bash `ssh`, not Windows PowerShell 5.1. PowerShell strips embedded double quotes, which turns `"a|b"` into a real pipe.
  - Never `pkill -f <pattern>` over ssh. It matches the remote shell's own command line and kills it, so the remaining commands silently don't run. Kill by PID instead.
  - Closing the VMware window suspends the VM. Resume it with `vmrun -T ws start <vmx> nogui`.
- Boot-test VM: `D:\GraceOS-vm\test\graceos-test.vmx`, with a fixed MAC `00:50:56:3A:00:01`. Its lease and hostname show up in `C:\ProgramData\VMware\vmnetdhcp.leases`.

## Next actions
1. Confirm the first GitHub CI run passes.
2. Decide on a LICENSE. (T-009)
3. Review and merge T-006 and T-007 (delegated to Cline). Write the Intelligence Layer architecture doc (T-004).
