# Claude Code Instructions — ELSIAN-INVEST 4.0

> Repo-wide baseline for Claude Code sessions.
> This file is not the canonical contract for routing, gates, or role behavior.
> If there is any conflict, `VISION.md`, `docs/project/DECISIONS.md`, and `docs/project/ROLES.md` win in that order.

## 1. Current system

- The active system in this repository is **ELSIAN 4.0**.
- The active working contract is in `docs/project/ROLES.md`.
- `docs/project/KNOWLEDGE_BASE.md` is onboarding context, not a replacement for the contract.
- The default technical surface is the current 4.0 Module 1 stack, not the old 3.0 `deterministic/` module.
- 3.0 assets are historical reference only unless the user explicitly asks to inspect or recover them under the relevant decisions.

## 2. Default entrypoints

Use the custom commands in `.claude/commands/` as the active Claude Code entry surfaces:

- `/project:orchestrator` — main entrypoint for repo status, next steps, planning, and end-to-end execution.
- `/project:kickoff` — read-only briefing.
- `/project:director` — scope, prioritization, governance, and packaging.
- `/project:engineer` — clearly scoped Module 1 technical work.
- `/project:auditor` — review and independent verification.
- `/project:capacity-scout` — read-only empty-backlog discovery.

Historical 3.0 wrapper material is archived and must not be treated as active runtime guidance.

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
- Prefer `/project:orchestrator` when the request is ambiguous, cross-surface, or end-to-end.
- Use `/project:director` first for scope, priority, or governance decisions.
- Use `/project:engineer` direct only for clearly local Module 1 implementation work.
- Use `/project:auditor` direct only for explicit review or verification requests.
- Use `/project:capacity-scout` only for read-only discovery when backlog resolution requires it.
- Keep `docs/project/BACKLOG.md` as the only executable queue.
- Do not present 3.0 `deterministic/`, `engine/`, or old Phase 2 instructions as the active architecture of this repo.
- Do not push unless Elsian asks explicitly.

## 5. Platform notes

- Claude Code uses a flat subagent model (Agent tool). Only the orchestrator spawns children; children cannot spawn further children.
- Read-only roles (kickoff, auditor, capacity-scout) enforce their constraint by instruction. They must not use Edit, Write, or mutating Bash commands.
- The governance checker (`python3 scripts/check_governance.py --format json`) is the primary source of live repo state.
- Auto-commit is owned exclusively by the orchestrator after green closeout.

## 6. Language and user

- Always respond in Spanish unless the user writes in English.
- The user's name is Elsian.
