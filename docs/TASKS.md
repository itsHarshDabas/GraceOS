# GraceOS task board

Claim a task by putting your name in **Owner** in your branch's first commit. Status values: `todo`, `in progress`, `review`, `done`, `blocked`.
Each brief is meant to be pasted directly to a coding agent (Claude Code, OpenCode, Cline). The agent must also follow `AGENTS.md`.

| ID | Task | Directory | Owner | Status | Depends on |
|---|---|---|---|---|---|
| T-001 | Build the ISO and boot-test it in a VM | `iso/`, `build/` | Harsh | done (UEFI and BIOS boot verified in VMware; console not observed) | — |
| T-002 | Make `boot-test.sh` reliable, then enable CI on push | `build/`, `.github/` | Harsh | review (passes locally; CI not yet run) | T-001 |
| T-003 | Grace Shell: framework ADR and first prototype | `desktop/` | Shell lead | in progress | — |
| T-004 | Intelligence Layer architecture doc | `docs/intelligence-layer.md` | Harsh | todo | — |
| T-005 | Agent Hub: adapter core and two adapters | `services/agent-hub/` | unassigned | todo | — |
| T-006 | Model manager: GGUF metadata and memory estimate | `services/model-manager/` | Harsh (Cline) | in progress, branch `ai/gguf-metadata` | — |
| T-007 | Hardware detection CLI (read-only) | `services/hardware-detection/` | Harsh (Cline) | in progress, branch `services/hardware-detection` | — |
| T-008 | Desktop foundation: KDE Plasma package set for the live ISO | `iso/` (separate branch) | unassigned | todo | T-001 |
| T-009 | Choose a LICENSE | repo root | Harsh (owner decision) | blocked | — |
| T-010 | Security review of `build/` and `iso/` | review only | unassigned | todo | T-001 |

---

## Briefs

### T-002 — reliable boot test
Goal: `build/boot-test.sh <iso> bios|uefi` exits 0 only when the live system reaches a shell, and non-zero otherwise.
Known issue: the stock kernel command line has no `console=ttyS0`, so the serial-console grep never matches. Options are to add `console=tty0 console=ttyS0,115200` to the boot entries in `iso/efiboot`, `iso/grub` and `iso/syslinux`, or to detect boot by a different means. Explain your choice. Also verify the OVMF path on current Arch (`pacman -Ql edk2-ovmf`).
Acceptance: passes for both modes on a freshly built ISO, run inside Arch; the CI workflow switches to `on: [push, workflow_dispatch]`; the PR shows the output.

### T-003 — Grace Shell (Shell lead)
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
Goal: a branch adding a minimal Plasma Wayland session to the live ISO (official packages only, verified with `build/check-packages.sh`), autologin to Plasma for the live user, and the measured ISO size and RAM use at idle.
Acceptance: the ISO builds and boots to Plasma in a VM; the numbers go in the PR. This is a temporary foundation, not the Grace Shell.

### T-010 — Security review
Goal: a read-only review of `build/*.sh`, `iso/airootfs`, `iso/profiledef.sh` and the CI workflow. Look for unsafe `rm -rf`, unquoted paths, root login and SSH defaults in the live ISO, and secrets.
Deliverable: findings as a PR comment or `docs/reviews/<date>-security.md`, each with severity and a suggested fix. No code changes in the same PR.
