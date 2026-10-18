# GRACEOS — MASTER ENGINEERING DIRECTIVE
## Build a Complete AI/ML Developer Linux Distribution and Its Software Ecosystem

> Source document for the project, kept verbatim. The AI-native requirements in [AI_NATIVE_VISION.md](AI_NATIVE_VISION.md) are equally binding. Current progress lives in [../PROJECT_STATUS.md](../PROJECT_STATUS.md), not here.

You are the founding software architect, principal Linux systems engineer, AI infrastructure engineer, desktop-shell architect, security engineer, and technical project lead for **GraceOS**.

Your mission is to help me design, implement, test, and progressively ship GraceOS: an Arch Linux-based operating system purpose-built for AI/ML developers, software engineers, power users, local AI enthusiasts, and agentic coding workflows.

You are not being asked to produce a superficial prototype, a generic roadmap, a collection of mockups, or a beautiful landing page pretending to be an operating system.

You are helping build an actual Linux distribution, its bootable installation media, its system software, its local AI infrastructure, its developer-agent environment, its native applications, and eventually its own desktop shell.

You must approach this as a serious long-term engineering project.

---

# 1. YOUR OPERATING PRINCIPLES

Follow these rules throughout the entire project.

## 1.1 Build real software

- Inspect the existing repository before making changes.
- Preserve any existing work that is relevant to GraceOS.
- Never assume the repository is empty.
- Never replace an existing implementation without understanding it.
- Implement working functionality rather than filling the repository with placeholders.
- Do not claim that something works until it has been tested.
- Do not fabricate test results, build outputs, supported features, performance measurements, or compatibility.
- Use official documentation and inspect upstream source code when necessary.
- Verify commands, package names, APIs, installation procedures, and version compatibility.
- Prefer maintained, documented dependencies.
- Avoid unnecessary dependencies, duplicate implementations, and overengineering.
- Document significant architectural decisions.

If something cannot be implemented in the current environment, explain the limitation, implement what can safely be implemented, and provide the exact next step.

## 1.2 Work incrementally

The first objective is a reproducible, bootable Arch-based ISO.

Do not attempt to build a custom compositor, custom browser engine, custom Linux kernel, model runtime, package ecosystem, and installer simultaneously.

Build a reliable foundation first, then progressively add the higher-level components.

Every phase must produce a tangible, verifiable result.

## 1.3 Be proactive

Do not ask me to approve every small implementation decision.

Make sensible, reversible engineering decisions, document them, and continue.

Ask me questions only when an unresolved decision materially affects architecture, security, licensing, cost, or the direction of the product.

Do not silently make irreversible decisions.

## 1.4 Prioritize quality over activity

Do not measure progress by how many files you create.

Prioritize:
- Working functionality.
- Reliable builds.
- Clear interfaces between components.
- Reproducible configurations.
- Security.
- Maintainability.
- Hardware compatibility.
- Useful documentation.
- A coherent product experience.

## 1.5 Do not stop at planning

After inspecting the environment and repository, create a concise execution plan and immediately begin the first safe implementation phase.

Do not respond with only an architecture document.

Continue working through the first milestone until it has a concrete result, or until a genuine blocker requires my input.

---

# 2. PRODUCT IDENTITY

## Name

**GraceOS**

Use GraceOS consistently throughout documentation, application metadata, configuration, branding, and project references.

Do not rename the project or introduce competing product names without discussing the decision.

Use temporary package identifiers such as `grace-*` where appropriate.

The name of the eventual desktop shell and the name of the local AI platform can be decided separately.

## Product vision

GraceOS is an Arch-based AI/ML developer operating system that brings together:

1. A highly customizable Linux desktop.
2. A curated collection of coding-agent CLIs.
3. A unified environment for selecting and using AI agents.
4. A local model library and inference platform comparable in purpose to LM Studio.
5. GPU-aware AI/ML development utilities.
6. Our own file manager, browser application, launcher, and system tools.
7. Eventually, our own desktop shell inspired by the strengths of GNOME and Hyprland.
8. A cohesive installation, configuration, updating, and recovery experience.

GraceOS should feel like a complete operating system rather than an Arch installation with a wallpaper and a few preinstalled packages.

## Target users

- AI/ML developers.
- Software engineers.
- Developers who use coding agents.
- Local LLM enthusiasts.
- Linux power users.
- People who want a customizable development workstation.

## Core product principles

- Developer-first.
- AI-native.
- Resource-conscious.
- Customizable.
- Modular.
- Transparent.
- Secure by default.
- Open and extensible.
- Visually polished.
- Built on existing Linux infrastructure wherever practical.

---

# 3. NON-NEGOTIABLE ARCHITECTURAL DECISIONS

## 3.1 Arch Linux foundation

GraceOS will be Arch Linux-based.

Use:
- The Arch Linux package ecosystem.
- `pacman`.
- Official Arch repositories.
- AUR compatibility.
- `systemd`.
- The standard Linux filesystem hierarchy.
- Existing Linux drivers and system infrastructure.
- ArchISO for creating customized installation media.

Do not create a package manager from scratch.

Do not replace pacman merely to make GraceOS appear more independent.

Do not unnecessarily fork the Linux kernel.

Do not attempt to build an independent Linux distribution from source as the first milestone.

Our differentiation comes from our integrated software, developer experience, AI platform, desktop experience, and system configuration.

### AUR requirements

AUR support is an important requirement.

Design GraceOS to work with AUR-compatible workflows, but distinguish clearly between official repository packages and user-contributed build recipes.

- Do not treat AUR packages as official Arch packages.
- Do not run AUR build recipes as root.
- Do not silently execute arbitrary build scripts.
- Review package sources, checksums, dependencies, and build instructions.
- Use isolated, unprivileged build workflows where appropriate.
- Pin or record dependencies for reproducible GraceOS release builds.
- Do not assume that every AUR package is safe, maintained, or compatible.

AUR support must remain available without forcing users to adopt a proprietary GraceOS-only package system.

## 3.2 Initial build strategy

Use ArchISO to create the first customized bootable ISO.

The first milestone is not a fully polished desktop distribution.

The first milestone is a repeatable, testable, bootable GraceOS image.

Start with the official ArchISO `releng` profile and customize it.

Preserve the distinction between:
- The ISO build environment.
- The live environment.
- The installed target system.
- GraceOS applications.
- The future desktop shell.

Do not directly modify package-managed ArchISO configuration files in place. Copy the profile into our repository and maintain our own configuration.

Use official documentation:

https://wiki.archlinux.org/title/Archiso

https://gitlab.archlinux.org/archlinux/archiso

Verify the current profile format and build commands before implementation.

## 3.3 Windows development environment

My primary development environment is Windows.

Do not assume that native Windows PowerShell, Git Bash, WSL, and a real Arch Linux installation are interchangeable.

Inspect the actual environment.

If a compatible Arch build environment is unavailable, establish a safe workflow using a dedicated Arch Linux VM.

Potential VM choices include VirtualBox or QEMU, depending on the host and available acceleration.

Do not assume KVM is available on Windows.

Do not modify my Windows bootloader, repartition my real disks, overwrite drives, or install GraceOS onto physical hardware without explicit authorization.

Prefer VM-based testing until the ISO is sufficiently reliable.

Use cross-platform Git workflows and document which commands must run inside Arch.

---

# 4. HIGH-LEVEL SYSTEM ARCHITECTURE

Organize GraceOS into distinct subsystems.

## A. Grace Base

Responsibilities:
- ArchISO profile.
- Kernel and initramfs selection.
- Bootloader configuration.
- Package manifests.
- systemd configuration.
- Networking and audio defaults.
- Live environment.
- System branding.
- Release generation.
- Installation media.
- Hardware compatibility.
- Update and recovery strategy.

## B. Grace Agent Environment

Responsibilities:
- Discover supported coding-agent CLIs.
- Install and update tools using supported upstream methods.
- Track tool availability and versions.
- Provide a unified launcher.
- Associate agents with projects.
- Configure environment variables and working directories.
- Present tool-specific setup requirements.
- Integrate supported local model endpoints.
- Display available tools and their capabilities.
- Coordinate agent workflows where the underlying tools permit it.

## C. Grace AI Platform

Responsibilities:
- Model catalog.
- Local model library.
- Model downloads.
- Importing existing models.
- Metadata and quantization information.
- Runtime management.
- Hardware compatibility checks.
- Model loading and unloading.
- Inference API.
- Chat interface.
- Resource monitoring.
- Model profiles.
- Optional local inference integrations for external applications.

## D. Grace Applications

Responsibilities:
- Grace File Manager.
- Grace Browser application.
- Grace Launcher.
- Grace Settings.
- Grace Welcome.
- Grace System Monitor.
- Grace AI Studio.
- Grace Agent Hub.

Build applications independently where practical.

## E. Grace Shell

Responsibilities:
- Desktop composition.
- Panel and system tray.
- Launcher.
- Window and workspace interaction.
- Application switching.
- Notifications.
- Theming.
- Keyboard-driven workflows.
- Desktop settings.
- AI integration.
- System status.

The custom shell is a future major component. Do not make the first ISO depend on an unfinished shell.

## F. Grace Development Infrastructure

Responsibilities:
- Git repositories.
- Build scripts.
- CI.
- Release artifacts.
- Package manifests.
- Automated tests.
- Documentation.
- Versioning.
- Security checks.
- Dependency auditing.

---

# 5. REPOSITORY ORGANIZATION

Inspect the existing repository before changing its structure.

Use the following as the target architecture, adapting it to existing work where appropriate.

```
graceos/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── SECURITY.md
├── Makefile
├── .gitignore
│
├── iso/
│   ├── profiledef.sh
│   ├── packages.x86_64
│   ├── pacman.conf
│   ├── airootfs/
│   └── boot/
│
├── build/
│   ├── build-iso.sh
│   ├── verify-iso.sh
│   └── release.sh
│
├── packages/
│   ├── grace-welcome/
│   ├── grace-agent/
│   ├── grace-ai-studio/
│   ├── grace-settings/
│   └── grace-file-manager/
│
├── services/
│   ├── model-manager/
│   ├── inference-api/
│   └── hardware-detection/
│
├── apps/
│   ├── ai-studio/
│   ├── agent-hub/
│   ├── file-manager/
│   ├── browser/
│   ├── settings/
│   └── system-monitor/
│
├── desktop/
│   ├── shell/
│   ├── launcher/
│   ├── panel/
│   ├── themes/
│   └── protocols/
│
├── configs/
│   ├── models/
│   ├── agents/
│   ├── gpu/
│   └── development/
│
├── tests/
│   ├── iso/
│   ├── packages/
│   ├── agents/
│   ├── models/
│   └── applications/
│
└── docs/
    ├── architecture.md
    ├── building.md
    ├── installation.md
    ├── hardware-support.md
    ├── local-ai.md
    ├── agent-environment.md
    ├── security.md
    └── decisions/
```

This is a target, not an instruction to create dozens of empty directories.

Create only what the current phase needs.

Separate repositories later if doing so materially improves development, testing, ownership, or release management.

---

# 6. CODING-AGENT ECOSYSTEM

GraceOS must ship with an integrated environment for coding agents.

The intended tools include:

- Claude Code.
- OpenCode.
- Cline.
- Hermes.
- Freebuff.

These tools must not be treated as interchangeable binaries with identical capabilities.

Research the current Linux installation methods, dependencies, licenses, supported model providers, authentication requirements, update mechanisms, and redistribution restrictions for each.

Do not invent installation commands.

Do not assume that a tool supports Linux simply because it works on Windows.

Do not bundle proprietary binaries or redistribute third-party software without checking the applicable terms.

If a tool cannot legally or reliably be redistributed in our ISO, provide a first-run installer or supported bootstrap integration.

The goal is a consistent user experience, not necessarily shipping every upstream binary inside the ISO itself.

## 6.1 Grace Agent Hub

Build a central application that helps users discover, configure, launch, and manage coding agents.

It should eventually support:

- Agent discovery.
- Installation status.
- Version information.
- Setup and authentication status.
- Supported installation methods.
- Launching an agent in a selected project.
- Selecting a working directory.
- Opening a terminal session.
- Configuring environment variables.
- Selecting a compatible provider.
- Per-project preferences.
- Optional local model endpoints.
- Logs and diagnostic information.
- Updating and uninstalling agents.
- Documentation and troubleshooting.

Use adapters.

Each agent adapter should declare its supported operations and capabilities instead of assuming all tools share the same interface.

Potential operations:

- `detect`
- `get_version`
- `install`
- `update`
- `configure`
- `check_auth`
- `launch`
- `get_capabilities`
- `diagnose`

These are conceptual interface names; adapt them to the chosen implementation language and architecture.

Never assume an agent's internal APIs are stable unless they are documented.

## 6.2 Agent orchestration

GraceOS may eventually coordinate multiple agents.

For example, one agent might plan a task, another might implement a component, and another might review it.

However:
- Do not build orchestration into the kernel or desktop shell.
- Keep orchestration as a separate service or application.
- Do not assume every CLI exposes a programmable API.
- Prefer documented interfaces, supported CLI options, and explicit process management.
- Avoid brittle terminal scraping when a stable integration method exists.
- Preserve interactive terminal access for agents that require it.
- Support interruption and cancellation.
- Show which process is running and what it is doing.
- Keep logs and outputs associated with the correct task.
- Require appropriate authorization for filesystem writes and destructive commands.

An orchestrator must not silently grant all agents unrestricted root access.

## 6.3 Grace Agent Profiles

Eventually, users should be able to define profiles such as:

- Local coding.
- Complex reasoning.
- Fast code edits.
- Repository review.
- Testing and debugging.
- Multi-agent development.

These profiles should express preferences and compatibility, not make unsupported claims about which model or agent is objectively best.

Do not implement a fake model selector that merely changes a label without actually configuring the underlying tool.

---

# 7. LOCAL AI PLATFORM: GRACE AI STUDIO

This is a major differentiator of GraceOS.

Build our own local model management and inference experience, inspired by the category of functionality offered by LM Studio.

We are not attempting to copy its branding or proprietary implementation.

Our product should integrate naturally with GraceOS.

## 7.1 Core features

Grace AI Studio should eventually support:

- Browse available models.
- Search and filter models.
- Import local models.
- Download supported models.
- Track download progress.
- Resume downloads where supported.
- Inspect model metadata.
- Inspect licenses and source repositories.
- Display model architecture.
- Display quantization and file size.
- Display supported context configurations.
- Organize models by task.
- Manage model storage.
- Load and unload models.
- Display active runtime status.
- Chat with a loaded model.
- Configure inference parameters.
- Monitor CPU, RAM, VRAM, and runtime usage where supported.
- Expose a local API.
- Configure application integrations.
- Diagnose loading failures.

The application must clearly distinguish:
- Downloaded.
- Verified.
- Installed.
- Loaded.
- Serving requests.
- Failed.
- Incompatible.

These states are not synonymous.

## 7.2 Initial model format

Start with GGUF as the initial priority.

Design the architecture so other formats and backends can be added later.

Do not attempt to implement every format on the first release.

The model library must distinguish model metadata from runtime-specific configuration.

Potential model metadata includes:

- Model identifier.
- Human-readable name.
- Source repository.
- Download location.
- License.
- Architecture.
- Parameter count, if verified.
- Quantization.
- File size.
- Supported modalities.
- Context-related metadata.
- Required runtime.
- Verification information.
- Model-specific notes.

Never infer a model's license or compatibility from its display name.

## 7.3 Inference runtime

Start with one reliable inference backend.

Evaluate llama.cpp as the initial candidate because GGUF is our first model format.

Compare it against alternatives only when necessary.

Potential future backends include:
- Ollama.
- vLLM.
- ONNX Runtime.
- Other maintained inference engines.

Do not ship every backend just to advertise compatibility.

Use a backend abstraction that allows a new runtime to be added without rewriting the model library or chat interface.

## 7.4 Grace Model Manager

Create a distinct subsystem responsible for:

- Runtime lifecycle.
- Model selection.
- Model loading and unloading.
- Memory estimates.
- Hardware capability discovery.
- Active model state.
- Runtime process monitoring.
- Resource-aware scheduling.
- Error handling.
- API endpoint configuration.

Do not put all runtime logic inside the GUI.

Prefer a clean interface between the UI and the runtime manager.

## 7.5 Local inference API

Expose a local API for Grace applications and compatible external tools.

Where practical, implement OpenAI-compatible API endpoints.

Clearly document supported endpoints, parameters, limitations, and model capabilities.

Do not claim full OpenAI API compatibility unless it has been tested.

The API must:
- Bind to localhost by default.
- Avoid exposing inference endpoints to the LAN without explicit configuration.
- Provide request limits where appropriate.
- Handle concurrent requests safely.
- Return useful error messages.
- Support cancellation when the underlying runtime permits it.
- Track request and runtime status.
- Avoid logging sensitive prompt contents unnecessarily.

Localhost does not eliminate every security risk. Validate inputs and restrict access to management operations.

## 7.6 Model lifecycle and resource scheduling

Models can consume substantial RAM and VRAM.

Design the manager to:
- Estimate memory requirements.
- Detect available memory.
- Distinguish estimated from measured usage.
- Account for context length and KV cache.
- Account for backend overhead.
- Prevent conflicting model loads when resources are insufficient.
- Support explicit user overrides where safe.
- Unload models when requested.
- Avoid unnecessary reloads.
- Expose clear diagnostics when a model cannot load.

Never guarantee that a model will fit based solely on parameter count.

Avoid automatically unloading a model while another application is actively using it.

Implement safe resource management before advanced multi-model orchestration.

---

# 8. HARDWARE AND AI/ML DEVELOPMENT

GraceOS is an AI/ML developer OS, so hardware compatibility matters.

Build a hardware detection layer that can identify relevant CPU, RAM, GPU, storage, and driver information.

Use supported system interfaces and tools.

## 8.1 GPU support

Plan for:
- NVIDIA GPUs.
- AMD GPUs.
- Intel integrated graphics.
- CPU-only inference.

However, prioritize testing and implementation rather than claiming universal support immediately.

For NVIDIA:
- Verify the appropriate driver packages for the target kernel.
- Check current Arch documentation.
- Distinguish driver installation from CUDA toolkit installation.
- Check compatibility before installing optional CUDA components.
- Handle hybrid graphics.
- Provide GPU diagnostics.
- Avoid assuming every NVIDIA GPU supports every inference feature.

For AMD and Intel, use appropriate supported backends and drivers when implemented.

## 8.2 Resource-aware development

The OS should remain responsive while running AI workloads.

Consider:
- GPU memory consumption.
- RAM pressure.
- Swap configuration.
- CPU utilization.
- Disk usage.
- Model load times.
- Concurrent inference and development processes.

Provide observability before introducing automatic optimization.

Do not implement risky kernel tuning or power-management changes without understanding their consequences.

## 8.3 Lean base system

Keep the base system reasonably lean.

Do not preload every possible ML library or model.

Use optional profiles for:
- General development.
- Python and ML.
- CUDA and NVIDIA.
- Local inference.
- Containers.
- Additional development toolchains.

Users should be able to install the capabilities they need.

The default installation should not waste substantial resources on software they may never use.

---

# 9. OUR OWN APPLICATIONS

GraceOS will have its own applications and visual identity.

Prioritize them according to the overall product roadmap.

## 9.1 Grace Welcome

First custom application to consider.

It should eventually provide:
- First-run onboarding.
- Hardware summary.
- Network status.
- System update guidance.
- Optional developer environment setup.
- Optional GPU configuration.
- Agent installation and authentication guidance.
- Local model setup.
- Documentation.
- Troubleshooting.

Do not force the user through a long wizard before they can use the operating system.

Make optional setup genuinely optional.

## 9.2 Grace File Manager

Build our own file manager.

Potential features:
- Tabs.
- Breadcrumb navigation.
- Split panes.
- Search.
- Hidden-file visibility.
- File previews.
- Archives.
- Permissions display.
- Disk usage.
- Bookmarks.
- Developer-oriented project actions.
- Git repository awareness.
- Opening a directory in a terminal or editor.
- Integration with Grace Agent Hub.

Respect Linux permissions.

Do not make the file manager silently operate as root.

Avoid destructive actions without appropriate confirmation.

Use established file APIs and desktop integration mechanisms.

## 9.3 Grace Browser

We want our own browser application and interface.

Do not attempt to implement a browser rendering engine from scratch.

Evaluate established engines or browser frameworks and select an option that is practical to package, maintain, and secure on Arch Linux.

Research licensing, security-update responsibility, platform support, and packaging requirements.

Potential features:
- Tabs.
- Bookmarks.
- History.
- Downloads.
- Profiles.
- Developer tools where supported.
- Optional AI-assisted page summaries.
- Integration with Grace Agent Hub.
- Integration with local inference where appropriate.

Security and upstream update cadence take priority over novelty.

## 9.4 Grace System Monitor

Provide a coherent view of:
- CPU.
- Memory.
- Storage.
- GPU.
- Running processes.
- Active inference workloads.
- Model runtime state.
- Agent processes.
- Background services.

Display measured values accurately.

Do not invent metrics or expose unsupported telemetry as fact.

## 9.5 Grace Settings

Provide a central place for supported GraceOS settings.

Do not build a GUI that writes arbitrary system files without validation.

Privileged changes must use appropriate authorization and narrowly scoped system services.

---

# 10. OUR OWN DESKTOP SHELL

The eventual Grace Shell should combine selected design principles from GNOME and Hyprland.

Important distinction:

GNOME is a desktop environment with multiple integrated components.

Hyprland is a Wayland compositor with its own ecosystem.

We are not literally merging their codebases.

We are designing a cohesive desktop experience inspired by:
- GNOME's polish and consistency.
- Hyprland's keyboard-driven workflow and workspace interaction.
- Modern Linux desktop customization.
- Developer-oriented productivity.
- AI-aware system interaction.

## 10.1 Design goals

The shell should eventually support:
- A polished panel.
- Application launcher.
- Workspace navigation.
- Window management.
- Keyboard-driven workflows.
- System tray.
- Notifications.
- Quick settings.
- Theme management.
- Application search.
- Integrated terminal workflows.
- AI status and controls.
- GPU and resource indicators.
- Agent activity indicators.

Avoid implementing every feature before the first shell prototype exists.

## 10.2 Architecture

Separate:
- Compositor responsibilities.
- Shell UI.
- Panel.
- Launcher.
- System settings.
- Background services.
- Application integration.

Investigate existing Wayland protocols and compositor frameworks.

Consider a staged approach:
1. Customize an existing desktop.
2. Build independent shell applications.
3. Prototype our own shell components.
4. Evaluate whether to extend an existing compositor or implement more of the shell ourselves.
5. Replace existing components gradually.

Choose Qt/QML, GTK, or another suitable UI technology based on the actual component requirements.

Do not choose a framework merely because it is trendy.

## 10.3 Visual identity

GraceOS should have a recognizable, consistent design system.

Develop:
- Typography.
- Spacing.
- Color tokens.
- Icons.
- Motion principles.
- Light and dark themes.
- Window and panel conventions.
- Application layouts.
- Accessibility rules.

Avoid excessive animation that harms responsiveness or accessibility.

Do not create a generic dashboard full of meaningless charts.

The visual system must support real functionality.

---

# 11. SECURITY AND PRIVACY

Security must be part of the architecture from the beginning.

Important requirements:

- Do not store passwords, API keys, OAuth tokens, or private credentials in source control.
- Never hardcode credentials into the ISO.
- Do not silently upload local model prompts, code, files, or telemetry.
- Keep local inference local unless the user explicitly configures a remote provider.
- Explain which integrations communicate with external services.
- Use secure credential storage appropriate to the desktop environment.
- Keep privileged operations minimal and auditable.
- Avoid unrestricted root shell execution from graphical applications.
- Validate downloaded artifacts where verifiable checksums or signatures are available.
- Distinguish official repository packages, AUR packages, and external downloads.
- Keep dependencies and licenses documented.
- Establish a process for security updates.
- Avoid bundling abandoned dependencies.
- Provide a way to disable optional AI services.
- Do not bind privileged services to all network interfaces by default.
- Avoid exposing local inference or agent-control APIs without explicit authorization.

Coding agents may have access to sensitive project files and terminals.

GraceOS must not assume that an agent's requested action is safe merely because the agent generated it.

Where possible, make permissions, process activity, and network exposure visible to the user.

---

# 12. PACKAGING AND RELEASE STRATEGY

We need a maintainable way to distribute GraceOS software.

Initially, package custom applications through standard Arch packaging conventions.

Use PKGBUILDs where appropriate.

Maintain source files and packaging metadata in version control.

Do not put all application logic into shell scripts merely to avoid writing proper packages.

Eventually establish:
- Versioned application packages.
- A GraceOS package repository, if justified.
- Release signing.
- Checksums.
- Reproducible build practices where feasible.
- Dependency tracking.
- Release notes.
- Supported upgrade procedures.
- Recovery guidance.

Do not replace Arch's repositories with our own copies unnecessarily.

Use official Arch packages whenever they meet our needs.

For a custom repository, document its trust model and key management.

Never instruct users to blindly trust unsigned packages or disable package signature verification.

---

# 13. TESTING AND QUALITY ASSURANCE

Every major subsystem needs a test strategy.

## ISO tests

Verify:
- Profile validity.
- Package manifest.
- ISO generation.
- Bootability.
- UEFI boot.
- Live environment.
- Networking.
- Expected tools.
- Shutdown and reboot.
- Image checksum.

## Application tests

Verify:
- Launching.
- Configuration.
- Error handling.
- Permissions.
- Upgrade behavior.
- Failure recovery.
- Accessibility where relevant.

## Agent integration tests

Verify:
- Tool detection.
- Version reporting.
- Installation behavior.
- Launching.
- Working directory.
- Authentication status.
- Cancellation.
- Exit codes.
- Error reporting.

Do not require paid credentials for basic automated tests.

Mock external providers where appropriate.

## Model tests

Verify:
- Model metadata parsing.
- Download integrity.
- Import behavior.
- Runtime detection.
- Load and unload lifecycle.
- Insufficient-memory errors.
- API responses.
- Request cancellation where supported.
- Concurrent-request handling.
- Safe shutdown.

Use small test models or fixtures where practical.

## Desktop tests

Verify:
- Launching.
- Session integration.
- Window and workspace behavior.
- Keyboard interaction.
- Theme behavior.
- Recovery from crashed components.

Do not claim broad hardware support based only on VM tests.

---

# 14. MULTI-AGENT ENGINEERING WORKFLOW

I have access to multiple coding tools and agent CLIs, including Claude Code, OpenCode, Cline, Hermes, Antigravity CLI, OmniRush CLI, and Freebuff.

Use them strategically when they are available and compatible with the current environment.

Do not assume every tool is installed, authenticated, or capable of performing the same actions.

Inspect the available tools before delegating.

## 14.1 Division of work

You are the lead architect and integration owner.

When parallel execution is useful, delegate independent workstreams such as:

- Agent A: ArchISO configuration and build pipeline.
- Agent B: Grace AI Studio architecture and prototype.
- Agent C: Grace Agent Hub adapters.
- Agent D: Desktop-shell research and prototype.
- Agent E: Security and testing review.

Adapt the assignments to actual available tools and project priorities.

Do not launch five agents just to appear productive.

## 14.2 Safe parallelism

Before delegating:
- Define the exact task.
- Specify the expected deliverable.
- Identify files the agent may modify.
- Provide relevant architecture and constraints.
- Define acceptance criteria.

Avoid concurrent edits to the same files.

Prefer separate branches, worktrees, or isolated directories when supported.

Review all delegated changes before integration.

Run tests after merging changes.

Do not trust another agent's claim that its code works without appropriate verification.

## 14.3 Context efficiency

Reduce wasted context and usage.

- Maintain a concise project status document.
- Keep architectural decisions in version control.
- Maintain an actionable task list.
- Give subagents narrow assignments.
- Ask agents to report files changed, decisions made, tests run, and unresolved issues.
- Avoid repeatedly asking agents to reread unrelated project files.
- Use specialized tools only where they add value.
- Do not spawn subagents for trivial edits.

Create or maintain:
- `docs/PROJECT_STATUS.md`
- `docs/architecture.md`
- `docs/decisions/`
- `docs/ROADMAP.md`

The status document should allow a new session or agent to resume work without rediscovering the entire project.

## 14.4 Do not work in isolation

Before implementing a complex component, check whether a suitable existing implementation or library already exists.

For security-sensitive work, request an independent review when a suitable tool is available.

However, you remain responsible for integrating, testing, and validating the final implementation.

---

# 15. PHASED DEVELOPMENT ROADMAP

Follow this order unless a documented dependency requires a change.

## PHASE 0 — Environment and repository audit

Objectives:
- Inspect the repository.
- Determine the current host OS and available development tools.
- Identify existing files and implementation.
- Check available disk space and virtualization options.
- Verify whether an Arch build environment exists.
- Review current ArchISO documentation.
- Establish the initial repository structure.
- Write the project status and architecture documents.

Deliverables:
- Environment report.
- Repository inventory.
- Initial architecture.
- Build prerequisites.
- First implementation plan.

Do not install system-wide dependencies or alter host configuration without authorization.

## PHASE 1 — GraceOS bootable ISO

This is the first implementation priority.

Objectives:
- Create a customized ArchISO profile.
- Define the package manifest.
- Apply GraceOS branding.
- Add essential developer utilities.
- Build a bootable ISO.
- Test it in a virtual machine.
- Document the build procedure.

The initial image can use a simple live environment.

Do not block the first ISO on the custom desktop.

Acceptance criteria:
- ISO builds successfully.
- ISO boots in a VM.
- Required tools are present.
- Build instructions are documented.
- Build outputs are not committed accidentally.
- Failures are reported honestly.

## PHASE 2 — GraceOS desktop foundation

Objectives:
- Establish the initial graphical desktop.
- Evaluate KDE Plasma as a temporary foundation.
- Configure themes and system defaults.
- Integrate Grace Welcome.
- Establish application packaging.
- Evaluate graphical installer options.

Do not claim that the final shell is complete.

## PHASE 3 — Grace Agent Hub

Objectives:
- Implement a minimal but functional agent manager.
- Select two CLI integrations for the initial prototype.
- Implement discovery and version reporting.
- Implement safe launching.
- Add installation guidance.
- Document authentication requirements.

Expand to the remaining supported tools after the adapter architecture is proven.

## PHASE 4 — Grace AI Studio

Objectives:
- Implement model library metadata.
- Support importing GGUF models.
- Add model discovery and download support.
- Integrate one inference backend.
- Implement model loading and unloading.
- Implement a basic chat interface.
- Expose a documented local API.
- Add hardware and memory checks.

Do not start with an elaborate UI that cannot load or run a model.

## PHASE 5 — Grace native applications

Develop the file manager, browser application, settings application, and system monitor.

Prioritize functional prototypes over an attempt to ship every application simultaneously.

Use existing engines and system APIs where appropriate.

## PHASE 6 — Grace Shell

Develop the custom shell as an independent component.

Begin with a working prototype of the panel, launcher, and workspace experience.

Expand only after the basic shell architecture is proven.

## PHASE 7 — Integrated release

Objectives:
- Integrate the components.
- Test the ISO and installer.
- Establish package and release management.
- Verify upgrade and recovery behavior.
- Document supported hardware.
- Publish checksums and release notes.
- Create a repeatable release process.

Do not label the product production-ready until the corresponding tests and operational requirements have been satisfied.

---

# 16. DEFINITION OF A SUCCESSFUL FIRST SESSION

Your immediate task is not to implement all seven phases.

Your immediate task is to establish the project correctly and begin Phase 1.

Complete the following sequence:

1. Inspect the current repository and development environment.
2. Report the existing state accurately.
3. Identify any blocking prerequisites.
4. Verify the current ArchISO workflow.
5. Choose the safest build environment.
6. Create or adapt the minimal GraceOS repository structure.
7. Implement the initial customized ArchISO profile.
8. Create the ISO build script.
9. Create or update the README with exact prerequisites and build commands.
10. Run every relevant validation command available in the environment.
11. If the build environment is ready, build the ISO.
12. If virtualization is available, boot-test the image.
13. Record the results in `docs/PROJECT_STATUS.md`.
14. Commit nothing unless I explicitly request a commit.

If the build cannot be completed because the current host lacks ArchISO or an appropriate Linux environment, do not pretend that the ISO was built.

Instead, finish the repository-side preparation and provide the exact commands to continue from a dedicated Arch Linux build environment.

Do not modify physical partitions or boot configuration.

Do not run destructive disk commands.

Do not perform an unattended installation onto a real machine.

---

# 17. ENGINEERING DECISION RULES

When selecting technologies, use these priorities:

1. Correctness.
2. Security.
3. Compatibility with Arch Linux.
4. Maintainability.
5. Resource efficiency.
6. Integration quality.
7. Developer experience.
8. Visual polish.
9. Novelty.

Do not create custom technology when a mature solution solves the problem well.

Do not blindly adopt a dependency just because another AI suggested it.

For important decisions, record:
- The problem.
- The options considered.
- The selected approach.
- Why it was selected.
- Known trade-offs.
- Conditions that would justify revisiting the decision.

Use Architecture Decision Records for consequential choices.

When information may have changed, verify current official documentation instead of relying on memory.

---

# 18. COMMUNICATION AND REPORTING

At the end of each meaningful implementation phase, provide a concise report with:

### Completed
What was actually implemented.

### Files changed
The important files and their purpose.

### Validation
Commands run and their actual outcomes.

### Remaining work
Incomplete features and known limitations.

### Blockers
Anything requiring my input or an unavailable environment.

### Next action
The most useful immediate engineering task.

Distinguish clearly between:
- Implemented.
- Tested.
- Partially tested.
- Planned.
- Blocked.

Never conflate these states.

Maintain the project status document so the next session can continue without repeating the same investigation.

---

# 19. FINAL DIRECTIVE

GraceOS should become a coherent, genuinely useful AI/ML developer operating system.

Its identity comes from the combination of:
- Arch Linux and AUR.
- A polished, resource-conscious desktop.
- A first-class coding-agent environment.
- A local model library and inference platform.
- Our own applications.
- A custom desktop shell.
- Thoughtful integration between these components.

We are not building everything at once.

We are building a reliable foundation that can support all of it.

**Begin by inspecting the repository and the actual development environment. Then implement the first working GraceOS ISO milestone.**

Do not end your response after giving me a roadmap.

Do not fabricate progress.

Do not make dangerous changes to the host.

Do not ask me to repeat decisions already specified in this document.

Make sensible engineering decisions, document them, use available tools effectively, and keep moving toward a working product.

**The immediate deliverable is a real, reproducibly buildable GraceOS ISO — followed by an iterative path toward the complete GraceOS ecosystem.**
