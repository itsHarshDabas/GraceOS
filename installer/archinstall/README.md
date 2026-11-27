# Grace Candyland in Arch's own installer

Install Grace Candyland from the **official Arch Linux ISO** with its stock `archinstall`.
No GraceOS ISO needed. From the Arch ISO's root prompt (online):

```sh
K=https://raw.githubusercontent.com/itsHarshDabas/GraceOS/main/packages/graceos-keyring
curl -fsSLO "$K/graceos.gpg"
pacman-key --add graceos.gpg
pacman-key --lsign-key "$(curl -fsSL "$K/graceos-trusted" | cut -d: -f1)"
curl -LO https://raw.githubusercontent.com/itsHarshDabas/GraceOS/main/installer/archinstall/grace_candyland.py
archinstall --config-url https://raw.githubusercontent.com/itsHarshDabas/GraceOS/main/installer/archinstall/grace-candyland.json
```

The first four lines make the Arch ISO trust the key that signs `[graceos]` (archinstall installs
with the ISO's keyring); `grace-candyland-desktop` then brings `graceos-keyring`, which adds the
key to the new system for updates. Compare the fingerprint with the one in
[`graceos-trusted`](../../packages/graceos-keyring/graceos-trusted) if you want to be sure.

archinstall's normal guided menu opens with these filled in, and you choose the rest
(disk, user, password, locale, timezone) as usual:

| Setting | Value |
|---|---|
| Profile | Desktop → **Grace Candyland** (from `grace_candyland.py`) |
| Packages | `grace-candyland-desktop` (the shell, CottonCandy, ToffeeTwirl, CherryColaLLM, Cortex Council, Ollama and what Grace Settings uses), `polkit`, `qt6-wayland` |
| Greeter | SDDM, which offers the **Grace Candyland** session |
| Graphics | All open-source (change it in the menu for NVIDIA) |
| Repos | `[graceos]` (`https://github.com/itsHarshDabas/GraceOS/releases/download/repo-x86_64`) |
| Network, audio, Bluetooth | NetworkManager, PipeWire, Bluetooth on |

The system keeps the name **Arch Linux**; only GraceOS's own ISO installs `graceos-release`.

## Why two commands
The config points archinstall at the profile file by `path`. archinstall can load that file
straight from a URL, but a bug in current archinstall drops profiles loaded that way
(`ProfileHandler._import_profile_from_url` removes them and never adds them back), so the
profile is downloaded first and loaded from the current directory. The fix is drafted in
[`docs/upstream/archinstall.md`](../../docs/upstream/archinstall.md). Once a release has it,
`path` can become the raw URL and the first command goes away.

## Why it isn't in archinstall's own menu (yet)
archinstall's built-in profiles install only packages from Arch's official repos, and its
README rules out AUR packages ("archinstall will not offer or bundle AUR helpers or AUR
packages due to a current consensus"). So a built-in Grace Candyland profile needs
`grace-candyland` (and the apps) in `[extra]` first, which only an Arch package maintainer can
do. The plan and the profile ready for that day are in `docs/upstream/archinstall.md`.

## Tested
- `grace_candyland.py` and `grace-candyland.json` loaded through archinstall's own
  `ProfileConfiguration.parse_arg` (archinstall master `2c25540`, Python 3.14): profile
  "Desktop" with "Grace Candyland" selected, its packages, SDDM, All open-source.
- Not yet run: a full install in a VM from the Arch ISO.
