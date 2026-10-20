# 0006: GraceOS's own packages come from a pacman repo on GitHub Releases

- Status: accepted by Harsh, 2026-10-19. Supersedes the file-copy step in ADR 0005.

## Context
Installed systems got Grace Candyland and the GraceOS `os-release` by copying files from the live ISO. pacman didn't know about them, so `pacman -Syu` never updated the desktop, and an update of Arch's `filesystem` package put "Arch Linux" back into `/usr/lib/os-release`. Users also expect an AUR helper on an Arch-based distro.

## Decision
- `packages/` holds the PKGBUILDs for what isn't in Arch's repos:
  - `graceos-release`: the GraceOS `os-release` (kept at `/usr/lib/graceos/os-release`), the desktop autostart on tty1, and the zram defaults.
  - `grace-candyland`: the desktop, at the commit pinned in `iso/candyland.ref`.
  - `cherrycola`: the local model CLI and chat app, at the [CherrySoda](https://github.com/itsHarshDabas/CherrySoda) commit pinned in `iso/cherrysoda.ref` (it lived in `services/cherrycola` until 2026-10-21).
  - `yay-bin`: the AUR helper, vendored unchanged from the AUR.
- **Name guard:** `/usr/lib/os-release` belongs to Arch's `filesystem` package, so we don't fight over the file. A pacman hook in `graceos-release` copies the GraceOS version over it after every install or upgrade of `filesystem` (and of `graceos-release` itself).
- `build/build-packages.sh` builds them into `out/repo`, a repo named `graceos`. The `packages` workflow runs it on every change and publishes the result as the `repo-x86_64` release, which is the repo's server URL.
- The ISO build and installed systems use that repo: `iso/pacman.conf` has `[graceos]`, and `graceinstall` passes it to archinstall as a custom repository, which writes it into the new system's `pacman.conf`. `build-iso.sh` uses `out/repo` instead when it exists, for local work.

## Consequences
- `pacman -Syu` updates GraceOS's own packages, and the name stays GraceOS.
- `graceinstall` no longer patches archinstall internals or copies files.
- **Unsigned for now** (`SigLevel = Optional TrustAll`): packages come over HTTPS from GitHub, but nothing proves who built them. Signing needs a key kept in a CI secret; required before a public release.
- Building the ISO needs the repo to exist: run the `packages` workflow (or `build/build-packages.sh`) first.
