# 0009: GraceOS Net, a smaller online image that downloads pinned packages at first boot

- Status: proposed, 2026-11-23. Harsh asked for "a smaller online-install ISO that needs connecting to the internet, then downloads all the tools and then boots". Claude designed and built it.
- Task: T-025.

## Context
The Full ISO is about 1.9 GB, just under GitHub's 2 GiB release-file limit (PR #15). Most of it is the desktop and the GraceOS apps. `graceinstall` already installs over the internet with either edition, so the packages on the ISO only serve the live session.

What Harsh asked for:
- a second image beside the Full ISO, which stays as it is;
- it needs the internet on first boot, so setup must handle Ethernet and Wi-Fi;
- it then downloads the tools (CottonCandy, CandySole, ToffeeTwirl, CherryCola, Ask Grace, Grace Settings, Cortex Council) and boots into the desktop;
- installs should be reproducible: pinned versions with verified checksums, not "whatever is newest", and download failures retried.

## Options
- **A. Download from Arch's mirrors and the rolling `repo-x86_64` release.** Simplest. Rejected: the live base is frozen on the ISO, so installing today's desktop onto last month's base is an Arch partial upgrade, which can break on a library bump. It also isn't reproducible.
- **B. Pin everything to the build.** Chosen.
  - The Net ISO is built from one day of the [Arch Linux Archive](https://wiki.archlinux.org/title/Arch_Linux_Archive) (`archive.archlinux.org/repos/YYYY/MM/DD`).
  - The ISO carries that day's `core` and `extra` databases and the build's `graceos.db`, so the base and the downloads always match.
  - The GraceOS packages are published with the ISO.
- **C. A netinstall that boots straight into `graceinstall`, with no live desktop.** Rejected. Harsh wants it to boot into the desktop, and `graceinstall` already covers installing.

## Decision
- **One profile, two editions.** `build/build-iso.sh net` reuses `iso/`, keeps the package list up to the end of the `[minimal]` GraceOS section and adds `networkmanager`. The desktop and AI sections are written to `/usr/share/graceos-net/packages` for download.
  - It copies `iso/net/airootfs` over the profile: `grace-net-setup`, a `profile.d` hook and a Net MOTD.
  - It renames the image `graceos-net-<date>-x86_64.iso` (label `GRACEOS_NET_*`, boot entries "GraceOS Net live medium").
  - The Full build is unchanged.
- **Pinning.**
  - The archive day is yesterday (UTC), or the most recent day that exists, or `ARCH_SNAPSHOT=YYYY/MM/DD`.
  - In the build's `pacman.conf`, each Arch repo lists the normal mirrors first, then the archive day.
    - The shipped databases fix the version of every package, and pacman checks each file's sha256 against them, so a mirror can only serve the exact pinned file.
    - Mirrors have most of those files (only packages updated since that day are gone) and are much faster. `archive.archlinux.org` is one server and stalled in the first CI run, so it serves only the rest.
  - `/usr/share/graceos-net/pacman.conf` is that same file with `[graceos]` pointing at `NET_REPO_URL`. In CI that is the `net-repo-<sha7>` release, which `publish-iso.sh` creates from the packages built in the same run.
  - `/usr/share/graceos-net/sync/` holds `core.db`, `extra.db` and `graceos.db`.
- **Verification.**
  - `grace-net-setup` copies the shipped databases into pacman's sync directory and installs without `-y`, so pacman never fetches newer databases.
  - pacman checks every package's sha256 from those databases, and Arch's signatures with the keyring that `pacman-init` sets up at boot. The ISO itself is checked with its `.sha256`, so trust runs from the ISO download to every package.
- **First boot.** On tty1, `00-grace-net.sh` runs `sudo grace-net-setup` before `grace-candyland.sh` starts the desktop.
  - It waits up to 30 s for Ethernet (NetworkManager does DHCP).
  - Without a connection, it offers a menu: Wi-Fi (scan with `nmcli`, pick a number, and nmcli asks for the password itself), `nmtui` for hidden Wi-Fi, mobile broadband, VPN or a static IP, try again, or stop and go to a shell.
  - It shows the download and installed sizes and checks that the live overlay has room.
  - It installs with up to 5 attempts and a doubling pause, re-checking the connection between them. pacman resumes partial downloads.
  - If this build's release was taken down (HTTP 404), it says the ISO is too old and links the latest release.
  - It then clears the package cache and marks itself done, and the desktop starts.
- **RAM.** The live session keeps the downloads in the archiso overlay, which is a tmpfs of 256 MiB by default. Net's boot entries set `cow_spacesize=75%`.
- **Release.** `build-iso.yml` builds, verifies and boot-tests `full` and `net` as a matrix. A `publish` job then:
  - uploads `net-repo-<sha7>` (a prerelease, never Latest);
  - uploads one `iso-<date>-<sha7>` release with both ISOs and their `.sha256` files;
  - deletes the older `iso-*` releases, as before;
  - keeps the newest five `net-repo-*` releases, so a Net ISO keeps working for a few releases after it is replaced.
- **Repository names.** Nothing hardcodes another repository. The GraceOS release URLs come from `github.repository` in CI, or from the `[graceos]` server in `iso/pacman.conf` for local builds.

## Consequences
- The Net ISO is smaller, but it needs the internet and more RAM than the Full ISO for the live desktop.
  - The size is not measured yet; the first CI build reports it.
  - The setup's "at least 6 GB" advice is an estimate until it's measured on a booted ISO.
- A Net ISO stops being able to finish setup once its `net-repo-*` release is pruned, after five newer builds. Setup then says so and links the latest ISO. `graceinstall` still works from it, because it installs from current mirrors like the Full ISO.
- Packages updated since the archive day come from `archive.archlinux.org`, a single server that can be slow. pacman moves on to the next server for a file that fails, and `grace-net-setup` retries the whole install.
- `graceinstall` is unchanged. An installed system uses the normal mirrors and the rolling `[graceos]` repo, not the pinned snapshot.
