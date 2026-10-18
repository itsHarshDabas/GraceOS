# GraceOS

An Arch Linux-based, AI-native operating system for AI/ML developers.

**Status: early.** Only the live-ISO foundation exists so far. Nothing here is a finished feature. See [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) for what has actually been built and tested.

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

## Layout
- `iso/`: a copy of the upstream archiso `releng` profile (commit 723da19), with GraceOS branding and a developer package block. `iso/symlinks.txt` lists the profile's symlinks, which the build recreates for Windows checkouts.
- `build/`: build, package-check and boot-test scripts.
- `docs/`: status, tasks, roadmap, architecture, decisions and vision.

Line endings are LF everywhere (enforced by `.gitattributes`).
