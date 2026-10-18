# Contributing to GraceOS

## Workflow
1. Pick or claim a task in `docs/TASKS.md`. Ask first if it is owned by someone else.
2. Branch from `main` as `<area>/<topic>` (`base/`, `shell/`, `ai/`, `agents/`, `apps/`, `docs/`).
3. Work only in that task's directory (see `AGENTS.md`). Commit small, focused changes.
4. Open a PR listing what changed, the commands you ran with their results, and open questions.
5. The other maintainer reviews it. Nothing merges to `main` unreviewed.

## Using coding agents (Claude Code, OpenCode, Cline)
- Every agent reads `AGENTS.md`. Claude Code picks it up via `CLAUDE.md`, OpenCode reads it directly, and Cline via `.clinerules`.
- Give an agent **one task brief** from `docs/TASKS.md`, not the whole project. Run independent tasks in parallel, in separate branches or worktrees (`git worktree add ../graceos-<task> -b <branch>`).
- Two agents must never edit the same files at the same time.
- Verify what an agent produced: run its tests and read the diff. An agent saying "done" proves nothing.
- Cline auto-approves actions by default, so always point it at the task directory.

## Building
See `README.md`. ISO builds need Arch Linux (a VM is fine) or the `build-iso` GitHub workflow.

## Decisions
Record anything hard to reverse as an ADR in `docs/decisions/NNNN-title.md` (problem, options, choice, trade-offs, when to revisit).
