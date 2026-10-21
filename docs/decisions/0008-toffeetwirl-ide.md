# 0008: ToffeeTwirl, the GraceOS IDE, is VS Code built with VSCodium's scripts, packaged from its own releases

- Status: accepted, 2026-10-21. Proposed by Claude; Harsh asked Claude to build, package and ship it. He forked VSCodium as [`itsHarshDabas/ToffeeTwirl-IDE`](https://github.com/itsHarshDabas/ToffeeTwirl-IDE), and chose "rebrand + Grace AI built in" for the first version. The command is `twirl`.
- Task: T-023.

## Context
GraceOS is for AI/ML developers, so it needs a first-class IDE. The dock pinned `code` (Code - OSS), which isn't on the ISO.

GraceOS's rules apply here too:
- It must work without AI.
- Network services bind to localhost.
- Model output is an untrusted proposal.
- Code from the user's files is data, and goes to no remote service.

## Options
- **A. Arch's `code` package (Code - OSS) plus our extension.** It's in `extra`, so there's nothing to build. But it uses Microsoft's names and Arch's system Electron, and it has no ToffeeTwirl identity.
- **B. Our VSCodium fork, built by its own workflow; GraceOS repackages the release tarball.** Chosen.
  - VSCodium's scripts build Microsoft's MIT-licensed source with telemetry removed and Open VSX for extensions. The fork adds the ToffeeTwirl names, icons and the built-in `grace` extension.
  - The fork's `ToffeeTwirl - Linux` workflow builds Linux x64 (`bin/twirl`) on GitHub's runners, and a manual run with "publish" makes a GitHub release.
  - `packages/toffeetwirl` installs that tarball into `/opt/toffeetwirl`, the same way the AUR's `vscodium-bin` does.
- **C. Build VS Code from source in GraceOS's `packages` workflow.** Rejected. It adds about an hour and roughly 10 GB of disk to every package build, and every ISO build, for a tarball that only changes when ToffeeTwirl does.

## Decision
- `packages/toffeetwirl/PKGBUILD` downloads the release `ToffeeTwirl-linux-x64-<version>.tar.gz`, pinned by version and sha256 in the PKGBUILD. It installs:
  - the app in `/opt/toffeetwirl`, with `/usr/bin/twirl` pointing at it;
  - `twirl.desktop`, whose name matches the window's Wayland app id and X11 class (`twirl`, from VS Code's `desktopName`);
  - the URL handler `twirl-url-handler.desktop`, for `toffeetwirl://` sign-in callbacks.
- Its dependencies are VS Code's own Linux list (`build/linux/debian/dep-lists.ts`) mapped to Arch packages, plus `libsecret` for the keyring. `cherrycola` is optional.
- `chrome-sandbox` isn't made setuid. Arch's kernels allow unprivileged user namespaces, which Chromium's sandbox uses instead.
- The ISO's desktop section installs `toffeetwirl`, and Grace Candyland pins `twirl` in the dock.

## Consequences
- **Updates:** a new ToffeeTwirl means four steps.
  1. Merge VSCodium's changes into the fork (VS Code's monthly releases carry Electron's security fixes).
  2. Run the workflow with "publish".
  3. Bump `pkgver` and `sha256sums` here.
  4. The `packages` workflow republishes `[graceos]`.

  Until someone does that, GraceOS lags VSCodium. That's the main cost of a fork.
- **Only x86_64 is built.** macOS, Windows and other CPU architectures, the tunnel CLI and the remote server (REH) aren't built.
- **Integrity:** the tarball is checked against the sha256 in the PKGBUILD. Like the rest of `[graceos]`, it's unsigned until ADR 0006's signing lands.
- **Size:** the app is 566 MB installed (release 1.140.07069). Its tarball is 198 MB, roughly what it adds to the ISO.
- **Grace in the IDE follows GraceOS's rules:**
  - It reads code only when a Grace command runs, and passes it to the local `cherrycola` CLI on stdin as quoted data.
  - It refuses when `cherrycola.conf` points at another computer.
  - It writes plain text only.
  - It disappears with `ai = off`.
  - The IDE works the same without CherryCola.
