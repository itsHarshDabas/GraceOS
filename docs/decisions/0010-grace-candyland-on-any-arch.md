# 0010: Grace Candyland installs on any Arch system: a meta-package, the AUR and an archinstall profile

- Status: proposed, 2026-11-23 (PR `packages/grace-candyland-anywhere`).

## Context
Harsh wants anyone installing Linux to be able to choose Grace Candyland. GraceOS's packages are
already a pacman repo (ADR 0006), but on plain Arch `grace-candyland` alone leaves Grace Settings'
hardware pages empty (their back ends are optional dependencies), and the apps are separate.
Arch's official repos only take packages that an Arch package maintainer adopts, and archinstall's
built-in profiles only install official packages (its README rules out the AUR).

## Decision
- **`grace-candyland-desktop`**, a meta-package in `[graceos]`: the shell, the GraceOS apps, Ollama
  and everything the Settings pages use. It does not pull in `graceos-release`, so a plain Arch
  system keeps its name; that package stays GraceOS-only.
- **The AUR:** `build/aur.sh` turns `packages/*` into AUR packages (fixed `pkgver`, commit pins from
  `iso/*.ref`, `toffeetwirl` as `toffeetwirl-bin`); the `aur` workflow checks them on PRs and, on
  `main`, pushes them with the `AUR_SSH_PRIVATE_KEY` secret. `graceos-release` and `yay-bin` stay out.
- **archinstall from Arch's own ISO:** `installer/archinstall/` holds a desktop profile and a config
  for `archinstall --config-url`. Upstream gets a bug fix now (URL profiles are dropped) and a
  built-in profile only once the packages are in `[extra]` (`docs/upstream/archinstall.md`).
- `check-packages.sh` also checks every `depends` of `packages/*` against the Arch repos.

## Consequences
- One command on any Arch system; updates come through pacman or yay.
- AUR publishing needs Harsh's AUR account and key (steps in `docs/install-anywhere.md`).
- The AUR is unsigned by design (it builds from source); `[graceos]` is still unsigned (ADR 0006).
- apt and dnf are not covered yet; where each piece stands is in `docs/install-anywhere.md`.
