# GitHub Copilot Instructions — ELSIAN-INVEST 4.0

> Repo-wide baseline for generic Copilot sessions.
> This file is not the canonical contract for routing, gates, or role behavior.
> If there is any conflict, `VISION.md`, `docs/project/DECISIONS.md`, and `docs/project/ROLES.md` win in that order.

## 1. Current system

- The active system in this repository is **ELSIAN 4.0**.
- The active working contract is in `docs/project/ROLES.md`.
- `docs/project/KNOWLEDGE_BASE.md` is onboarding context, not a replacement for the contract.
- The default technical surface is the current 4.0 Module 1 stack, not the old 3.0 `deterministic/` module.
- 3.0 assets are historical reference only unless the user explicitly asks to inspect or recover them under the relevant decisions.

## 2. Default entrypoints

Use the wrappers in `.github/agents/` as the active Copilot entry surfaces:

- `elsian-orchestrator.agent.md` for repo status, next steps, planning, and end-to-end execution.
- `elsian-kickoff.agent.md` for read-only briefing.
- `project-director.agent.md` for scope, prioritization, governance, and packaging.
- `elsian-4.agent.md` for clearly scoped Module 1 technical work.
- `elsian-auditor.agent.md` for review and independent verification.
- `elsian-capacity-scout.agent.md` for read-only empty-backlog discovery.

Historical 3.0 wrapper material is archived outside `.github/agents/` and must not be treated as active runtime guidance.

## 3. Read first

Read these before substantial work:

1. `VISION.md`
2. `docs/project/ROLES.md`
3. `docs/project/KNOWLEDGE_BASE.md`

Read on demand when the task requires them:

- `docs/project/PROJECT_STATE.md`
- `docs/project/BACKLOG.md`
- `docs/project/DECISIONS.md`
- `docs/project/MODULE_1_ENGINEER_CONTEXT.md`
- `CHANGELOG.md`
- `python3 scripts/check_governance.py --format json`

## 4. Working rules

- Do not redefine routing, gates, anti-fraud, role contracts, or output formats here. Follow `docs/project/ROLES.md`.
- Prefer `elsian-orchestrator` when the request is ambiguous, cross-surface, or end-to-end.
- Use `project-director` first for scope, priority, or governance decisions.
- Use `elsian-4` direct only for clearly local Module 1 implementation work.
- Use `elsian-auditor` direct only for explicit review or verification requests.
- Use `elsian-capacity-scout` only for read-only discovery when backlog resolution requires it.
- Keep `docs/project/BACKLOG.md` as the only executable queue.
- Do not present 3.0 `deterministic/`, `engine/`, or old Phase 2 instructions as the active architecture of this repo.

## 5. Legacy note

- `docs/archive/github-agents/deterministic.agent.md` is archived reference material from the 3.0 deterministic workflow.
- If a user explicitly asks for 3.0 historical context, use it only as archived reference, never as the default operating contract for 4.0 work.
