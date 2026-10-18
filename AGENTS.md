# AGENTS.md — rules for every coding agent on GraceOS

Claude Code, OpenCode, Cline, and humans all follow this file. `CLAUDE.md` and `.clinerules` just point here.

## What this is
GraceOS: an Arch Linux-based, AI-native OS for AI/ML developers. It is built on ArchISO, pacman, AUR and systemd; we don't fork the kernel or replace the package manager.
The full requirements are in `docs/vision/MASTER_DIRECTIVE.md` and `docs/vision/AI_NATIVE_VISION.md`. Read the relevant section, not the whole thing.

## Before you start (read in this order, stop when you have enough)
1. `docs/PROJECT_STATUS.md`: what is built, what is tested, what is blocked.
2. `docs/TASKS.md`: find your task ID, its owner, its directory and its acceptance criteria.
3. `docs/architecture.md` and `docs/decisions/`: interfaces and settled decisions. Don't re-litigate them; propose a new ADR instead.

## Hard rules
- **Stay in your task's directory.** Don't edit files owned by another workstream (see the owner column in `docs/TASKS.md`). If you need a change there, write it up in your PR description.
- **One task, one branch:** `<area>/<short-topic>`, e.g. `shell/panel-prototype` or `ai/gguf-parser`. Never push to `main` directly.
- **Never claim something works unless you ran it.** Report results as *implemented / tested / partially tested / planned / blocked*, and paste the actual commands and their output.
- **No placeholders, no fake features.** A selector that only changes a label, or an empty stub claiming support, is not acceptable.
- **Don't invent install commands, package names, or APIs.** Verify them against official docs or `pacman -Si`. Use only official Arch repo packages in `iso/packages.x86_64`; AUR packages are never added there.
- **Security:** no secrets, tokens, or credentials in the repo or the ISO. Network services bind to localhost by default. Never use an unrestricted root shell from a GUI or from model output. AI output is an untrusted proposal until validated.
- **Must work without AI:** every feature needs a usable path with no model, provider, or network.
- **Don't commit build outputs:** `out/`, `work/`, `*.iso` and VM disks are gitignored. Keep it that way.
- **Line endings are LF** (`.gitattributes` enforces this). Shell scripts must stay executable (`git update-index --chmod=+x`).

## Environment facts
- The ISO builds **only on Arch Linux** (a VM is fine) or in the `build-iso` GitHub workflow. It does not build on Windows, Git Bash or WSL. Commands are in `README.md`.
- On Windows checkouts, git flattens symlinks into text files. `build/build-iso.sh` restores them from `iso/symlinks.txt`. If you add a symlink under `iso/`, add it to that manifest too.
- `iso/` is a copy of upstream archiso `releng` (commit 723da19). Keep changes minimal and documented, so upstream updates can be merged.

## Where things go
| Path | Contents | Owner |
|---|---|---|
| `iso/`, `build/`, `.github/` | ArchISO profile, build and test scripts, CI | Base (Harsh) |
| `desktop/` | Grace Shell, panel, launcher, themes | Shell lead |
| `services/<name>/` | Daemons and CLIs (agent-hub, model-manager, hardware-detection, …) | see `docs/TASKS.md` |
| `apps/<name>/` | GUI apps (welcome, ai-studio, file-manager, …) | see `docs/TASKS.md` |
| `docs/` | status, tasks, architecture, ADRs, vision | everyone (keep edits scoped) |

Create directories only when a task needs them.

## When you finish
1. Update your row in `docs/TASKS.md` (status), and `docs/PROJECT_STATUS.md` if you changed what is built or tested.
2. Open a PR listing: files changed, decisions made, commands run with their results, and open issues.
3. A different person or agent reviews before merge. Never merge your own unreviewed work.
