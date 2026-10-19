# GraceOS

An Arch Linux-based, AI-native operating system for AI/ML developers.

**Status: early.** The live ISO is set up to start the GraceOS desktop, [Grace Candyland](https://github.com/itsHarshDabas/grace-candyland) (Hyprland with a Quickshell shell, see [ADR 0004](docs/decisions/0004-grace-candyland-desktop.md)). Nothing here is a finished feature. See [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) for what has actually been built and tested.

## Start here
- [AGENTS.md](AGENTS.md): rules for humans and coding agents (Claude Code, OpenCode, Cline).
- [CONTRIBUTING.md](CONTRIBUTING.md): branch and PR workflow, and how to split work across agents.
- [docs/TASKS.md](docs/TASKS.md): the task board, with briefs ready to hand to an agent.
- [docs/vision/](docs/vision/): the full product requirements (master directive and AI-native vision).
- [docs/ROADMAP.md](docs/ROADMAP.md), [docs/architecture.md](docs/architecture.md), [docs/decisions/](docs/decisions/).

## Build the ISO
Needs a real Arch Linux environment (a VM is fine). It will not run on native Windows.
```
sudo pacman -S archiso
sudo build/check-packages.sh   # verify every package in the manifest exists
sudo build/build-iso.sh        # -> out/graceos-<date>-x86_64.iso (+ .sha256)
sudo build/verify-iso.sh out/graceos-*.iso          # checksum, branding, symlinks, required tools
build/boot-test.sh out/graceos-*.iso bios           # boots in QEMU and waits for sshd (needs qemu-base)
build/boot-test.sh out/graceos-*.iso uefi           # also needs edk2-ovmf
```
The `build-iso` GitHub Actions workflow runs the same steps in an Arch container on every push to `main` and every PR that touches `iso/`, `build/` or the workflow. It can also be triggered manually, and only manual runs keep the ISO as an artifact.

## Try it in a VM
Create a VM (VMware, VirtualBox, virt-manager or QEMU) with **UEFI** firmware, 4 GB of RAM, 2 or more CPUs and a 30 GB disk, and boot the ISO. The live session logs in as `grace` (no password, `sudo` works) and the desktop starts by itself in about a minute. It runs without 3D acceleration too, using software rendering. Press Super+Space to search apps, or open **Install GraceOS** there to install onto the VM's disk.

## Install GraceOS to a disk
Boot the ISO and run `sudo graceinstall` in a terminal, or open **Install GraceOS** from Ask Grace (Super+Space). It's archinstall's guided installer with GraceOS defaults filled in (see [ADR 0005](docs/decisions/0005-graceinstall-on-archinstall.md)): pick the disk, user and password, review, and install. It wipes the disk you choose, so pick carefully. After installing, log in on the first console and the desktop starts.

`sudo build/install-test.py out/graceos-*.iso` tests the installer end to end inside QEMU: an unattended install onto a blank virtual disk, then a boot and login with a screenshot of the desktop.

## Layout
- `iso/`: a copy of the upstream archiso `releng` profile (commit 723da19), with GraceOS branding and a developer package block. `iso/symlinks.txt` lists the profile's symlinks, which the build recreates for Windows checkouts.
- `build/`: build, package-check, verify, boot, desktop and installer test scripts.
- `installer/`: `graceinstall` and its tests (`python -m pytest installer/`).
- `docs/`: status, tasks, roadmap, architecture, decisions and vision.

Line endings are LF everywhere (enforced by `.gitattributes`).
