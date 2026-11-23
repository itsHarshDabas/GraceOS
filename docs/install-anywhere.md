# Grace Candyland on any Arch system (and what's next for other distros)

GraceOS's own ISO is one way to get Grace Candyland. These are the others.

## 1. An existing Arch install: the GraceOS repo
Add this to the end of `/etc/pacman.conf`:

```ini
[graceos]
SigLevel = Optional TrustAll
Server = https://github.com/itsHarshDabas/GraceOS/releases/download/repo-x86_64
```

Then:

```sh
sudo pacman -Syu grace-candyland-desktop
sudo systemctl enable --now NetworkManager bluetooth   # if they aren't on yet
```

Start it by picking **Grace Candyland** in a login screen (`sudo pacman -S sddm && sudo systemctl enable sddm`),
or by typing `grace-candyland` on a text console. For Ask Grace, download a model with
`cherrycolallm pull` (or from CherryColaLLM). Updates come with `pacman -Syu` as usual.

Want only part of it? Each piece is its own package: `grace-candyland` (the desktop), `cottoncandy`,
`toffeetwirl`, `cherrycolallm`, `cortex-council`.

> The repo isn't signed yet (`Optional TrustAll`): packages come over HTTPS from GitHub Releases,
> but nothing proves who built them. Signing is planned before a wider launch (ADR 0006).

## 2. An existing Arch install: the AUR
Once the packages are published there (the `aur` workflow; see "Publishing to the AUR" below):

```sh
yay -S grace-candyland-desktop
```

AUR names: `grace-candyland`, `cottoncandy`, `toffeetwirl-bin`, `cherrycolallm`, `cortex-council`,
`grace-candyland-desktop`. They build the same pinned commits as the `[graceos]` repo.

## 3. A fresh install from Arch's official ISO
Boot the normal Arch ISO, get online, and run:

```sh
curl -LO https://raw.githubusercontent.com/itsHarshDabas/GraceOS/main/installer/archinstall/grace_candyland.py
archinstall --config-url https://raw.githubusercontent.com/itsHarshDabas/GraceOS/main/installer/archinstall/grace-candyland.json
```

archinstall's guided menu opens with the Grace Candyland desktop profile, the `[graceos]` repo and
SDDM chosen; pick the disk and user and install. Details: [installer/archinstall/README.md](../installer/archinstall/README.md).

## What you get compared to GraceOS's ISO

| | GraceOS ISO / graceinstall | Arch + `grace-candyland-desktop` |
|---|---|---|
| Grace shell, Ask Grace, Grace Settings, CandySole, lock screen, theming | yes | yes |
| CottonCandy, ToffeeTwirl, CherryColaLLM, Cortex Council, Ollama | yes | yes |
| Settings pages (Wi-Fi, Bluetooth, sound, battery, brightness, Night Light) | yes | yes (their back ends are dependencies) |
| First-launch setup (`~/.config/grace`, lite mode on small PCs) | yes | yes, the same code |
| Desktop starts after logging in on tty1 | yes | no: use a login screen or type `grace-candyland` |
| Services on (NetworkManager, Bluetooth) | yes | archinstall route: yes; otherwise enable them |
| Name "GraceOS", fastfetch look, zram defaults, `grace-wine` | yes (`graceos-release`) | no: the system stays Arch Linux |
| yay | yes | install it yourself |

`graceos-release` can be installed on plain Arch too, but it renames the system to GraceOS; that's
what makes it GraceOS rather than Arch with Grace Candyland.

## Why not Arch's official repos
`[core]` and `[extra]` only take packages that an Arch package maintainer adopts and maintains, so
we can't upload there. The route is the AUR first; a maintainer may adopt popular, well-kept AUR
packages. Until then archinstall can't list Grace Candyland in its own menu, because its built-in
profiles only install official packages (see [docs/upstream/archinstall.md](upstream/archinstall.md)).

## Publishing to the AUR (one-time setup, Harsh)
1. Create an account at https://aur.archlinux.org/register.
2. Make a key just for it: `ssh-keygen -t ed25519 -f ~/.ssh/aur -C aur`.
3. On the AUR, **My Account → SSH Public Key**: paste `~/.ssh/aur.pub`, enter your password, **Update**.
4. In GitHub, GraceOS **Settings → Secrets and variables → Actions**:
   - secret `AUR_SSH_PRIVATE_KEY` = the contents of `~/.ssh/aur`;
   - variable `AUR_MAINTAINER` = `Harsh Dabas <you@example.com>` (shown in each PKGBUILD).
5. **Actions → aur → Run workflow.** The first push creates each package under your account; after
   that every change to `packages/` or `iso/*.ref` on `main` updates them.

If someone already owns one of the names, that push fails and the log says so; pick another name in
`build/aur.sh` (`AUR_NAME`).

## Other distros (apt, dnf)
The apps are also published as signed apt and dnf repos: see [install-apt-dnf.md](install-apt-dnf.md),
which also says which packages each Debian, Ubuntu and Fedora release can install.
