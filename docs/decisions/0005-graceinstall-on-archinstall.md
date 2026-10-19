# 0005: graceinstall is archinstall with GraceOS defaults

- Status: accepted by Harsh, 2026-10-19.

## Context
GraceOS needs an installer that feels like `archinstall`: a guided menu in the terminal that partitions a disk, creates a user and installs the system. Partitioning, encryption and bootloaders are where installers cause data loss, so we shouldn't write that part ourselves.

## Decision
`graceinstall` (`installer/graceinstall`, at `/usr/local/bin/graceinstall` on the ISO) runs archinstall's own guided script with:
- **GraceOS defaults pre-filled:** hostname `graceos`, NetworkManager, PipeWire, Bluetooth, UTC, and the GraceOS package list.
  - The package list comes from `iso/packages.x86_64`, everything after the first `# --- GraceOS` marker. `build-iso.sh` writes it to `/usr/share/graceinstall/packages`, so the ISO and installed systems get the same set.
  - The user can change every default in the menu, and a user `--config` is merged over them.
- **One GraceOS step:** just before archinstall runs its custom commands inside the new system, graceinstall copies in what isn't in the Arch repos. That is the Grace Candyland files, the GraceOS `os-release`, and `/etc/profile.d/grace-candyland.sh`, which starts the desktop after login on tty1.

## Alternatives considered
- **Calamares:** a graphical installer used by many Arch-based distros. It's heavier and needs a Qt session and its own module configuration. Could be added later for a graphical install.
- **A custom installer:** rejected; it would re-implement partitioning and bootloader setup.

## Consequences
- **Hooking archinstall's internals:** graceinstall patches `archinstall.scripts.guided.run_custom_user_commands`, an internal name. An archinstall update can break it; `build/install-test.py` catches that by running a full unattended install in QEMU.
- **Copied files aren't tracked by pacman,** so `pacman -Syu` won't update Grace Candyland, and an update of the `filesystem` package restores Arch's `os-release`. The fix is a GraceOS package repo with `grace-candyland` and `graceos-release` packages (T-016).
- **No graphical login screen yet.** The installed system boots to a text login on tty1, and the desktop starts after you log in.
