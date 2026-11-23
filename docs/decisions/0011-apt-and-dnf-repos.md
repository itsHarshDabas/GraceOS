# 0011: GraceOS's apps as signed apt and dnf repos on GitHub Releases

- Status: proposed, 2026-11-23 (PR `distro/apt-dnf-repos`). Harsh chose "own signed apt + dnf repos" over a PPA and COPR.

## Context
Harsh wants the apps installable with apt and dnf too. Debian's, Ubuntu's and Fedora's archives need a
sponsor inside each project. PPAs and COPR build from source on their servers without network access
for npm, which doesn't suit ToffeeTwirl (a prebuilt release) or Cortex Council (bundled node_modules).

## Decision
- `build/build-distro-packages.sh` builds `.deb` (dpkg-deb) and `.rpm` (rpmbuild) for cherrycolallm,
  cottoncandy, cortex-council, toffeetwirl, grace-candyland and grace-candyland-desktop, from the same
  pins as `packages/*`. Versions are `0.rN.sha7` for git builds.
- `build/make-distro-repos.sh` makes a flat apt repo and a dnf repo laid out as release assets:
  `apt-repo` (debs + signed `InRelease`), `rpm-repo` (signed rpms + `graceos.repo`) and `repodata`
  (so dnf's `baseurl` is `.../releases/download`, whose `repodata/repomd.xml` is the `repodata`
  release's asset). No GitHub Pages needed, like the pacman repo (ADR 0006).
- The `distro-packages` workflow install-tests every package in Debian sid and 13, Ubuntu 24.04 and
  devel, and Fedora, and publishes on `main` only when `GRACEOS_SIGNING_KEY` is set. Nothing unsigned is
  ever published.

## Consequences
- One key to guard (`GRACEOS_SIGNING_KEY`); it can sign the pacman repo later too.
- What each release can install depends on its archive (Quickshell, PySide6 Qt WebEngine, Node 22); CI
  reports it, `docs/install-apt-dnf.md` keeps the table.
- Ollama and the Updates & Software page stay Arch-only.
