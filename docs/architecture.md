# Architecture (target)
Subsystems: Grace Base (ArchISO, packages, branding), Agent Environment (adapters per coding-agent CLI), AI Platform (model manager, llama.cpp backend, localhost OpenAI-style API), Apps, Shell, Dev infra.
Grace Intelligence Layer: a separate service between UI/apps and providers/agents. It owns provider routing, scoped context, task plans, and approvals. Permissions are enforced outside the model; model output is an untrusted proposal; system actions are structured and validated, never a raw root shell. Not implemented yet.

## Ownership
Grace Shell (Phase 6, `desktop/`) is being developed separately by a collaborator. The ISO and all other subsystems must not depend on it; integration goes through documented interfaces only (launcher/panel protocols, the Intelligence Layer API).
