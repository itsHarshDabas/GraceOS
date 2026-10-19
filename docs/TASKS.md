# GraceOS task board

Claim a task by putting your name in **Owner** in your branch's first commit. Status values: `todo`, `in progress`, `review`, `done`, `blocked`.
Each brief is meant to be pasted directly to a coding agent (Claude Code, OpenCode, Cline). The agent must also follow `AGENTS.md`.

| ID | Task | Directory | Owner | Status | Depends on |
|---|---|---|---|---|---|
| T-001 | Build the ISO and boot-test it in a VM | `iso/`, `build/` | Harsh | done (UEFI and BIOS boot verified in VMware; console not observed) | — |
| T-002 | Make `boot-test.sh` reliable, then enable CI on push | `build/`, `.github/` | Harsh | review (passes locally; CI not yet run) | T-001 |
| T-003 | Grace Shell: framework ADR and first prototype | repo `grace-candyland`, ADR 0004 | Shell lead (v0 built by Harsh) | v0 done, Shell lead to review | — |
| T-004 | Intelligence Layer architecture doc | `docs/intelligence-layer.md` | Harsh | todo | — |
| T-005 | Agent Hub: adapter core and two adapters | `services/agent-hub/` | unassigned | todo | — |
| T-006 | Model manager: GGUF metadata and memory estimate | `services/model-manager/` | Harsh (Cline) | done (PR #2) | — |
| T-007 | Hardware detection CLI (read-only) | `services/hardware-detection/` | Harsh (Cline) | in progress, branch `services/hardware-detection` | — |
| T-008 | Desktop foundation for the live ISO | `iso/` | Harsh | done: Grace Candyland instead of KDE (ADR 0004) | T-003 |
| T-009 | Choose a LICENSE | repo root | Harsh (owner decision) | blocked | — |
| T-010 | Security review of `build/` and `iso/` | review only | unassigned | todo | T-001 |
| T-011 | Window title bars with traffic lights for every app | `grace-candyland` | unassigned | todo | T-003 |
| T-012 | Settings pages beyond Appearance (Wi-Fi, Displays, Sound, Power, AI & Models, Agents, About) | `grace-candyland` | unassigned | todo | T-003 |
| T-013 | Lock screen "Goodness GraceOS" and idle locking (polkit agent later) | `grace-candyland` | Harsh (Claude) | in progress | T-003 |
| T-014 | Make `grace-candyland` public so CI can clone it | GitHub settings | Harsh | done | — |
| T-015 | `graceinstall`: guided disk installer (archinstall + GraceOS defaults) | `installer/`, ADR 0005 | Harsh | v0 done; unattended QEMU install test in `build/install-test.py` | — |
| T-016 | GraceOS package repo: `graceos-release` (name survives updates), `grace-candyland`, `cherrycola`, `yay` | `packages/`, GitHub Releases | Harsh (Claude) | in progress | T-015 |
| T-017 | Graphical login screen (greeter) for installed systems | `grace-candyland` or `iso/` | unassigned | todo | T-015 |
| T-018 | CandySole: GraceOS's own terminal (GTK4 + VTE) | `grace-candyland/apps/candysole` | Harsh (OpenCode, reviewed by Claude) | in progress | — |
| T-019 | CherryCola: local model service and CLI (Ollama default, LM Studio supported) | `services/cherrycola` | Harsh (Cline, reviewed by Claude) | in progress | — |
| T-020 | Stock Wine (wine, wine-mono, wine-gecko, winetricks) | `iso/` | Harsh (Claude) | in progress | — |
| T-021 | Low-end PCs: automatic lite mode, zram, and a Minimal install choice | `grace-candyland`, `iso/`, `installer/` | Harsh (Claude) | in progress | T-016 |

---

## Briefs

### T-002 — reliable boot test
Goal: `build/boot-test.sh <iso> bios|uefi` exits 0 only when the live system reaches a shell, and non-zero otherwise.
Known issue: the stock kernel command line has no `console=ttyS0`, so the serial-console grep never matches. Options are to add `console=tty0 console=ttyS0,115200` to the boot entries in `iso/efiboot`, `iso/grub` and `iso/syslinux`, or to detect boot by a different means. Explain your choice. Also verify the OVMF path on current Arch (`pacman -Ql edk2-ovmf`).
Acceptance: passes for both modes on a freshly built ISO, run inside Arch; the CI workflow switches to `on: [push, workflow_dispatch]`; the PR shows the output.

### T-003 — Grace Shell (Shell lead)
Update 2026-10-19: Harsh asked for the shell to be built now as its own installable repo. A v0, Grace Candyland (Hyprland + Quickshell), is in `itsHarshDabas/grace-candyland`, with the choice recorded in ADR 0004. The Shell lead should review the ADR and the code, and own the shell from here. The original brief follows.

Goal: an ADR in `docs/decisions/` choosing the shell's technical base, then a prototype panel and launcher in `desktop/`.
Read section 10 of `docs/vision/MASTER_DIRECTIVE.md` and section 3 of `AI_NATIVE_VISION.md`.
Settle in the ADR: whether to extend an existing Wayland compositor (e.g. a wlroots-based one or Hyprland) or start from a toolkit-based shell; Qt/QML vs GTK vs another option; and how the shell talks to the future Intelligence Layer (assume a local IPC API; don't depend on it existing yet).
Constraints: the ISO must not depend on the shell. Install and run commands must be Arch-verified.
Acceptance: the ADR is merged; the prototype runs in an Arch VM with documented commands and a screenshot in the PR.

### T-005 — Agent Hub adapter core
Goal: a Python package `services/agent-hub/` (stdlib first, `pytest` for tests, managed with `uv`).
Interface: an `AgentAdapter` with `detect() -> bool`, `get_version() -> str | None`, `get_capabilities() -> set[str]`, and `launch(project_dir, extra_args) -> subprocess.Popen`. Capabilities are declared per adapter, not assumed.
Implement adapters for **Claude Code** and **OpenCode** using only their documented CLI flags. Detect via `shutil.which` plus `--version`. Install commands must come from official docs and live in the adapter as data, never executed automatically.
Add a CLI: `grace-agents list` prints name, installed, version and capabilities.
Acceptance: tests mock `subprocess` and `which`, with no network and no credentials; `uv run pytest` passes; the README documents what is and isn't supported.

### T-006 — Model manager: GGUF metadata and memory estimate
Goal: `services/model-manager/` (Python, stdlib first). Parse the GGUF header and metadata key/values (architecture, parameter-related fields, quantization type, context length) without loading tensors.
Add an `estimate_memory(model, context_len)` that returns **estimated** bytes with a breakdown (weights, KV cache, overhead) and labels the result as an estimate.
Follow the GGUF spec in the ggml repository (`docs/gguf.md`); link the spec version you used.
Acceptance: tests use a tiny GGUF fixture generated in the test with the official `gguf` Python package (a test dependency only), or a hand-built header; malformed files raise clear errors; `uv run pytest` passes.

### T-007 — Hardware detection CLI
Goal: `services/hardware-detection/`, a read-only `grace-hw` command that prints JSON describing the CPU (model, cores), RAM, GPUs (vendor, model, driver in use), and disks.
Use `/proc`, `/sys`, `lspci -k` and `lsblk -J`. Report a field as unknown rather than guessing it. No root required.
Acceptance: unit tests run the parsers against saved command outputs in `tests/fixtures/`; a real run on the GraceOS live ISO is pasted in the PR.

### T-008 — KDE Plasma live desktop (Phase 2 evaluation)
Superseded on 2026-10-19: the live ISO now ships Grace Candyland (ADR 0004). Kept for history.
Goal: a branch adding a minimal Plasma Wayland session to the live ISO (official packages only, verified with `build/check-packages.sh`), autologin to Plasma for the live user, and the measured ISO size and RAM use at idle.
Acceptance: the ISO builds and boots to Plasma in a VM; the numbers go in the PR. This is a temporary foundation, not the Grace Shell.

### T-010 — Security review
Goal: a read-only review of `build/*.sh`, `iso/airootfs`, `iso/profiledef.sh` and the CI workflow. Look for unsafe `rm -rf`, unquoted paths, root login and SSH defaults in the live ISO, and secrets.
Deliverable: findings as a PR comment or `docs/reviews/<date>-security.md`, each with severity and a suggested fix. No code changes in the same PR.

### T-011 — Title bars for every window
Hyprland draws no server-side decorations, so only apps with their own title bar (GTK, Grace Settings) show traffic lights. Evaluate the `hyprbars` plugin (hyprland-plugins, installed via `hyprpm`) against the design: buttons left, title centered, hairline, matching the accent rules. Acceptance: terminals and Qt apps get the same bar in a screenshot from an Arch VM.

### T-012 — Settings pages
Each listed page gets real controls backed by the system (NetworkManager, PipeWire, UPower, the model manager, Agent Hub), and every option maps to a documented key or system setting. Appearance is the reference for layout and behaviour.

### T-016 — GraceOS package repo
Installed systems get Grace Candyland and the GraceOS `os-release` by file copy (ADR 0005), so `pacman -Syu` doesn't update the first and an update of `filesystem` reverts the second. Build `grace-candyland` and `graceos-release` (provides `/usr/lib/os-release`, conflicts handled the way other Arch-based distros do) as packages, publish a signed repo (GitHub Releases is fine to start), add it to the ISO's and the installed system's `pacman.conf`, and switch `graceinstall` from copying files to installing packages. Acceptance: on an installed VM, `pacman -Syu` updates `grace-candyland` from the repo and `/usr/lib/os-release` still says GraceOS.

### T-013 — Lock screen
Quickshell `WlSessionLock` + `PamContext` (the `login` PAM stack). The lock surface shows the time, the date, **Goodness GraceOS**, the user, a password field and PAM's messages. Super+L locks, `hypridle` locks after 10 minutes idle and before suspend. Acceptance: in an Arch VM, Super+L locks every screen, a wrong password is rejected with a message, the right one unlocks, and killing the shell while locked leaves the session locked (the compositor's lock is not released).

### T-018 — CandySole
A GTK4 + libadwaita + VTE terminal in Python, installed by grace-candyland. Tabs, a right-click menu (Copy, Paste, Select All, New Tab, New Window, Open in Files, zoom), the usual Ctrl+Shift shortcuts, clickable links, Grace colors and Fira Code, `-e CMD` and `--working-directory`. It replaces Konsole as the default terminal. Acceptance: runs on Hyprland in an Arch VM with and without 3D, screenshot with a right-click menu open.

### T-019 — CherryCola
`cherrycola` talks to Ollama (default) or LM Studio's local server, stdlib-only Python. `ask`, `chat`, `status [--json]`, `models`, `pull [MODEL]`, `use MODEL`, `start`/`stop` (a per-user `ollama serve`, started on demand, never at boot). The default model is picked from RAM and only downloaded when the user runs `pull`. Ask Grace sends questions to it and the Local AI card shows its status. Acceptance: tests against fake Ollama and LM Studio servers pass with no network; on the live ISO, `cherrycola pull` then `cherrycola ask` answers.

### T-020 — Wine
`wine`, `wine-mono`, `wine-gecko` and `winetricks` from `extra` (Wine is WoW64 now, so no multilib). Acceptance: on the live ISO, `wine notepad` opens a window.

### T-021 — Low-end PCs
Lite mode turns off blur, shadows and animations automatically when there's no GPU or less than 4 GB of RAM. zram swap by default. `graceinstall` asks Full or Minimal; Minimal installs no desktop, CherryCola or Wine. Acceptance: idle RAM of the live desktop and of a Minimal install measured and recorded in PROJECT_STATUS.
