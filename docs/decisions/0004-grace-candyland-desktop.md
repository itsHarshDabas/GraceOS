# 0004: The desktop is Grace Candyland (Hyprland + Quickshell), in its own repo

- Status: accepted by Harsh, 2026-10-19. For review by the Shell lead (T-003).
- Design it implements: `docs/design/2026-10-19-grace-shell-design.md`.

## Context
The design asks for GNOME's calm look with Hyprland's compositor-level control (tiling, gaps, blur, animation), AUR theme compatibility, small optional AI touches, and agent approvals enforced outside the model. Harsh also asked for the shell to be installable on other distros, not only on GraceOS.

## Decision
- **Compositor: Hyprland.** It gives auto-tiling, equal gaps, rounding, blur, shadows and animations, configurable live through `hyprctl`. It is in Arch's official repos, and community themes, cursors and plugins already target it.
  - It's tested with 0.56.2.
  - Hyprland 0.56 made a Lua config the default. We keep the classic `hyprland.conf` format, which 0.56 still loads, because older Hyprland versions on other distros only read that format.
- **Shell UI: Quickshell (QML, Qt 6)**, in Arch `[extra]`. It has built-in support for Hyprland IPC and global shortcuts, layer-shell surfaces, a notification server, PipeWire, UPower and power profiles, NetworkManager, BlueZ and desktop entries. So the bar, control center, dock, launcher, notifications and Settings are plain QML with no extra daemons.
- **Separate repo: `itsHarshDabas/grace-candyland`.**
  - `make install` (with `PREFIX` and `DESTDIR`) works on any distro, and there's an Arch PKGBUILD.
  - GraceOS installs the commit pinned in `iso/candyland.ref` at ISO build time (`build/build-iso.sh`).
- **One settings file:** `~/.config/grace/desktop.conf`.
  - Settings edits it in place and the shell applies changes live.
  - Users' own Hyprland settings go in `~/.config/grace/hyprland.conf`, which loads last.
- **Agent approvals:** `grace-approve AGENT COMMAND [CWD]` blocks until the user picks Allow once or Deny in the shell.
  - Exit status 0 means allowed. Any other status, including "shell not running", means denied.
- **Live ISO:**
  - A `grace` user (passwordless sudo, as with root on the Arch ISO) autologins on tty1 and starts the desktop.
  - NetworkManager replaces systemd-networkd and iwd, because the Wi-Fi toggle talks to NetworkManager.

## Alternatives considered
- **Writing our own compositor** (wlroots or Smithay): years of work before it matches Hyprland.
- **A GNOME Shell extension:** it gets the look, but not compositor-level tiling and animation control, and it only runs on GNOME.
- **KDE Plasma** (the old T-008): heavy, and not the agreed look.
- **AGS/Astal or eww instead of Quickshell:** both viable. Quickshell had the most of what we need built in (notifications, PipeWire, NetworkManager, BlueZ, Hyprland IPC) and is in Arch's official repos.

## Consequences
- **Hyprland changes its config syntax between releases.** The config uses the current rule syntax (`blur on, match:namespace …`). CI runs `Hyprland --verify-config` on every push to catch breakage.
- **Hyprland draws no title bars,** so the design's traffic lights appear only in apps that draw their own (GTK, and Grace Settings). Follow-up: T-011.
- **Hyprland needs GPU acceleration.** If it fails to start, `grace-candyland` retries once with Mesa software rendering. That makes VMs without 3D usable, but slow.
- **Same-user enforcement only.** The approval answer travels through a user-only FIFO, so a malicious program already running as the user could answer its own request. Real enforcement needs agents to run as a separate user or in a sandbox (Intelligence Layer work).
- **CI needs the candyland repo to be public.** It's private for now, so `build-iso.sh` can't clone it in CI; use `CANDYLAND_SRC=/path/to/checkout` locally.
