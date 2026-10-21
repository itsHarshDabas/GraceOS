# GraceOS

An Arch Linux-based, AI-native operating system for AI/ML developers.

**Status: early.** The live ISO is set up to start the GraceOS desktop, [Grace Candyland](https://github.com/itsHarshDabas/grace-candyland) (Hyprland with a Quickshell shell, see [ADR 0004](docs/decisions/0004-grace-candyland-desktop.md)). Nothing here is a finished feature. See [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) for what has actually been built and tested.

## Download
The [Latest release](https://github.com/itsHarshDabas/GraceOS/releases/latest) has the newest ISO that passed the build's checks and its BIOS and UEFI boot tests. Every push to `main` that changes the ISO replaces it.
- GitHub limits release files to 2 GiB, so a bigger ISO comes in parts (`.part00`, `.part01`, …).
- Download every part and the `.sha256` into one folder, then run `cat graceos-*.iso.part* > graceos-<date>-x86_64.iso` and `sha256sum -c graceos-*.iso.sha256`.

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
build/build-packages.sh        # optional: GraceOS's own packages into out/repo (else the published repo is used)
sudo build/check-packages.sh   # verify every package in the manifest exists
sudo build/build-iso.sh        # -> out/graceos-<date>-x86_64.iso (+ .sha256)
sudo build/verify-iso.sh out/graceos-*.iso          # checksum, branding, symlinks, required tools
build/boot-test.sh out/graceos-*.iso bios           # boots in QEMU and waits for sshd (needs qemu-base)
build/boot-test.sh out/graceos-*.iso uefi           # also needs edk2-ovmf
```
The `build-iso` GitHub Actions workflow runs the same steps in an Arch container on every push to `main` and every PR that touches `iso/`, `build/`, `packages/` or the workflow. Runs on `main`, and manual runs, then publish the tested ISO as the Latest release (`build/publish-iso.sh`); manual runs also keep it as a workflow artifact for a week.

## Try it in a VM
Create a VM (VMware, VirtualBox, virt-manager or QEMU) with **UEFI** firmware, 4 GB of RAM, 2 or more CPUs and a 30 GB disk, and boot the ISO. The live session logs in as `grace` (no password, `sudo` works) and the desktop starts by itself in about a minute. It runs without 3D acceleration too, using software rendering. Press Super+Space to search apps, or open **Install GraceOS** there to install onto the VM's disk.

## Install GraceOS to a disk
Boot the ISO and run `sudo graceinstall` in a terminal, or open **Install GraceOS** from Ask Grace (Super+Space). It's archinstall's guided installer with GraceOS defaults filled in (see [ADR 0005](docs/decisions/0005-graceinstall-on-archinstall.md)). It first asks which GraceOS:
- **Full:** the Grace desktop, the CandySole terminal, CherryCola (local AI) and Wine.
- **Minimal:** no desktop, AI or Wine; close to a bare Arch install, for old or small PCs.

Then pick the disk, user and password, review, and install. It wipes the disk you choose, so pick carefully. After installing, log in on the first console and the desktop starts.

## Using GraceOS
- **Packages:** `sudo pacman -S <name>` from Arch's repos, `yay -S <name>` from the AUR. `sudo pacman -Syu` updates everything, GraceOS's own packages included ([ADR 0006](docs/decisions/0006-graceos-package-repo.md)), and the system keeps its GraceOS name.
- **Local AI:** `cherrycola pull` downloads a model sized for your RAM, then ask from Ask Grace (Super+Space) or with `cherrycola ask "..."` / `cherrycola chat`. It uses Ollama by default; with LM Studio's local server running, `cherrycola backend lmstudio` uses that instead. Nothing runs or downloads until you ask.
- **Windows apps:** `wine setup.exe`; `winetricks` for extra Windows components.
- **Lock the screen:** Super+L.

`sudo build/install-test.py out/graceos-*.iso` tests the installer end to end inside QEMU: an unattended install onto a blank virtual disk, then a boot and login with a screenshot of the desktop.

## Layout
- `iso/`: a copy of the upstream archiso `releng` profile (commit 723da19), with GraceOS branding and a developer package block. `iso/symlinks.txt` lists the profile's symlinks, which the build recreates for Windows checkouts.
- `build/`: build, package-check, verify, boot, desktop and installer test scripts.
- `installer/`: `graceinstall` and its tests (`python -m pytest installer/`).
- `packages/`: PKGBUILDs for GraceOS's own packages; `build/build-packages.sh` builds them into the `graceos` repo.
- CherryCola, the local model CLI and chat app, lives in its own repo, [CherrySoda](https://github.com/itsHarshDabas/CherrySoda). GraceOS builds the commit pinned in `iso/cherrysoda.ref`.
- `docs/`: status, tasks, roadmap, architecture, decisions and vision.

Line endings are LF everywhere (enforced by `.gitattributes`).
