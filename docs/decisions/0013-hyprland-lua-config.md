# 0013: Grace Candyland's Hyprland config is Lua (supersedes part of 0004)

- Status: proposed, 2026-11-24. Needs Harsh's OK (the shell lead owns `grace-candyland`).
- Change: grace-candyland PR #5, commit `076c2fb`.

## Context
ADR 0004 kept the classic `hyprland.conf` format so older Hyprland versions on other distros could still read it. Hyprland 0.57.0 (2026-10-28) removed that format, the `hyprctl keyword` command, and the old `hyprctl dispatch` syntax. Arch ships 0.57, so on GraceOS:
- Hyprland reads `hyprland.conf` as Lua and fails (`hyprland.conf:2: unexpected symbol near '#'`), and `make check` fails in grace-candyland CI, on `main` as well.
- Every live change the shell makes (gaps, blur, animations, input, monitors) went through `hyprctl keyword`, and the Dock, Control Center, Settings and idle used old-style dispatches.

## Decision
- Ship only `hypr/hyprland.lua`, checked with `Hyprland --verify-config` on 0.57.2.
- The shell applies settings with `hyprctl eval 'hl.config({...})'`, and dispatches with `hl.dsp.*`.
- Users' own settings move to `~/.config/grace/hyprland.lua`. Settings → Displays writes `monitors.lua`; `grace-candyland` converts an old `monitors.conf` once. An old personal `hyprland.conf` is not converted and needs rewriting by hand.

## Consequences
- **Hyprland older than 0.55 can't run Grace Candyland any more.** That matters for the apt and dnf packages (ADR 0012) on distros that ship an older Hyprland. If that's needed, `grace-candyland` could pick a legacy config by Hyprland version, but the shell would also need a second, `keyword`-based code path.
- A mistake in a user's `monitors.lua` or `hyprland.lua` is caught with `pcall` and shown as a Hyprland notification; the Grace defaults stay loaded.
