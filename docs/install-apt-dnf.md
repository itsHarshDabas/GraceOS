# GraceOS apps on Debian, Ubuntu and Fedora (apt and dnf)

GraceOS's apps are also built as `.deb` and `.rpm` packages, from the same pinned sources as the
pacman repo, and published as signed apt and dnf repos on this repo's GitHub Releases
(`build/build-distro-packages.sh`, `build/make-distro-repos.sh`, the `distro-packages` workflow).

## Debian and Ubuntu

```sh
sudo curl -fsSL -o /usr/share/keyrings/graceos-archive-keyring.gpg \
  https://github.com/itsHarshDabas/GraceOS/releases/download/apt-repo/graceos-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/graceos-archive-keyring.gpg] https://github.com/itsHarshDabas/GraceOS/releases/download/apt-repo ./" \
  | sudo tee /etc/apt/sources.list.d/graceos.list
sudo apt update
sudo apt install cherrycolallm toffeetwirl      # and the others your release supports (below)
```

## Fedora

```sh
sudo curl -fsSL -o /etc/yum.repos.d/graceos.repo \
  https://github.com/itsHarshDabas/GraceOS/releases/download/rpm-repo/graceos.repo
sudo dnf install cherrycolallm toffeetwirl cottoncandy cortex-council
```

## What installs where
The `distro-packages` workflow installs each package in a clean container and runs a smoke check
(`cherrycolallm --help`, PySide6 Qt WebEngine imports for CottonCandy, Node 22+ for Cortex Council,
`twirl --version`, and Hyprland, Quickshell and the shell files for Grace Candyland). Its log is the
current answer; the table is what we expect:

| Package | Debian 13 | Debian testing/sid | Ubuntu 24.04 | Ubuntu devel | Fedora |
|---|---|---|---|---|---|
| `cherrycolallm` | yes | yes | yes (tested) | yes | yes |
| `toffeetwirl` | yes | yes | yes (tested) | yes | yes |
| `cottoncandy` | maybe | yes | no: no PySide6 Qt WebEngine | maybe | yes |
| `cortex-council` | maybe (needs Node 22) | maybe | no: Node 18 | maybe | yes |
| `grace-candyland` | no: no Quickshell | maybe | no: no Quickshell or Hyprland | maybe | maybe |
| `grace-candyland-desktop` | no | maybe | no | maybe | maybe |

"maybe" turns into yes or no with the first CI run on these images.

Things that stay Arch-only: Ollama isn't in these archives (install it from https://ollama.com for
Ask Grace and CherryColaLLM), and Grace Settings' Updates & Software page reads pacman and yay.
CottonCandy doesn't make itself the default browser here, unlike on GraceOS.

## Versions
Git builds are `0.rN.sha7` (the same commit count and hash as the pacman packages), so a later tagged
release such as `1.0` sorts above them. ToffeeTwirl keeps its release version, the meta-package its date.

## One-time setup (Harsh): the signing key
Nothing is published until the repos can be signed.

1. Make a key just for packages (no passphrase, so CI can use it):
   ```sh
   gpg --batch --passphrase '' --quick-gen-key "GraceOS packages <you@example.com>" rsa4096 sign never
   gpg --armor --export-secret-keys "GraceOS packages" > graceos-signing.asc
   ```
   RSA keeps older rpm and apt versions able to check it.
2. In GitHub, GraceOS **Settings → Secrets and variables → Actions**, add the secret
   `GRACEOS_SIGNING_KEY` with the contents of `graceos-signing.asc`, then delete that file and keep
   a backup of the key somewhere offline. Losing it means every user has to re-import a new key.
3. **Actions → distro-packages → Run workflow.** It creates the `apt-repo`, `rpm-repo` and
   `repodata` releases; after that, every change to the pinned sources republishes them.

The same key can later sign the `[graceos]` pacman repo (ADR 0006).

## Why releases, not Debian, Ubuntu or Fedora themselves
Their official archives need a sponsor or packager inside each project. A Launchpad PPA or a COPR
only builds from source on their servers, with no network for npm, which doesn't fit ToffeeTwirl
(a prebuilt release) or Cortex Council (bundled npm modules). Our own signed repos need no new
accounts. If a distro packager picks the apps up later, these packages are a starting point.
