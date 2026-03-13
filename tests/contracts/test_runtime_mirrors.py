from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ROLE_PATH = REPO_ROOT / "docs/project/ROLES.md"
SCOUT_AGENT_PATH = REPO_ROOT / ".github/agents/elsian-capacity-scout.agent.md"
ORCHESTRATOR_AGENT_PATH = REPO_ROOT / ".github/agents/elsian-orchestrator.agent.md"
KICKOFF_AGENT_PATH = REPO_ROOT / ".github/agents/elsian-kickoff.agent.md"
DIRECTOR_AGENT_PATH = REPO_ROOT / ".github/agents/project-director.agent.md"

SCOUT_SKILL_PATH = Path("/Users/ismaelsanchezgarcia/.codex/skills/elsian-capacity-scout/SKILL.md")
ORCHESTRATOR_SKILL_PATH = Path("/Users/ismaelsanchezgarcia/.codex/skills/elsian-orchestrator/SKILL.md")
KICKOFF_SKILL_PATH = Path("/Users/ismaelsanchezgarcia/.codex/skills/elsian-kickoff/SKILL.md")
DIRECTOR_SKILL_PATH = Path("/Users/ismaelsanchezgarcia/.codex/skills/elsian-director/SKILL.md")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_roles_contract_documents_level_1_and_discovery_baseline() -> None:
    text = _read(ROLE_PATH)
    for snippet in (
        "**Nivel 1** — implementado completo en esta tranche",
        "## Discovery Baseline",
        "`pass_summary`",
        "`reconciliation_summary`",
        "`claimed_bl_status: none`",
    ):
        assert snippet in text


def test_capacity_scout_mirrors_share_output_json_and_partial_pass_contract() -> None:
    required = (
        "eval --all --output-json /tmp/elsian-capacity-scout/eval_report.json",
        "`pass_summary`",
        "`findings`",
        "`reconciliation_summary`",
        "`partial_pass`",
        "manifest_expected_absent",
    )
    for path in (ROLE_PATH, SCOUT_AGENT_PATH, SCOUT_SKILL_PATH):
        text = _read(path)
        for snippet in required:
            assert snippet in text, f"{snippet!r} missing in {path}"


def test_orchestrator_mirrors_reference_contract_driven_empty_backlog_routing() -> None:
    required = (
        "`pass_summary`, `findings`, and `reconciliation_summary`",
        "partial_pass = true",
        "baseline-only governance wave",
        "`run-next-until-stop`",
        "first BL fails",
    )
    for path in (ORCHESTRATOR_AGENT_PATH, ORCHESTRATOR_SKILL_PATH):
        text = _read(path)
        for snippet in required:
            assert snippet in text, f"{snippet!r} missing in {path}"


def test_director_mirrors_reference_batch_budget_and_baseline_wave() -> None:
    required = (
        "max `3` BLs",
        "max `1` `shared-core`",
        "`broad` item goes alone",
        "baseline-only governance wave",
        "`claimed_bl_status: none`",
    )
    for path in (DIRECTOR_AGENT_PATH, DIRECTOR_SKILL_PATH):
        text = _read(path)
        for snippet in required:
            assert snippet in text, f"{snippet!r} missing in {path}"


def test_kickoff_mirrors_keep_empty_backlog_resolution_non_terminal() -> None:
    required = (
        "`empty_backlog_discovery`",
        "baseline-only wave",
        "not sufficient",
    )
    for path in (KICKOFF_AGENT_PATH, KICKOFF_SKILL_PATH):
        text = _read(path)
        for snippet in required:
            assert snippet in text, f"{snippet!r} missing in {path}"
