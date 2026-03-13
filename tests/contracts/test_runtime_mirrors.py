from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ROLE_PATH = REPO_ROOT / "docs/project/ROLES.md"
BACKLOG_PATH = REPO_ROOT / "docs/project/BACKLOG.md"
OPPORTUNITIES_PATH = REPO_ROOT / "docs/project/OPPORTUNITIES.md"
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


def test_roles_contract_documents_packet_b_over_tranche_a() -> None:
    text = _read(ROLE_PATH)
    for snippet in (
        "Packet B — Investigacion y expansion como trabajo de primer nivel",
        "`investigation_BL_ready`",
        "`expansion_candidate`",
        "`packageable_count`",
        "## Resumen ejecutivo",
        "`pass_summary`",
        "`reconciliation_summary`",
        "`claimed_bl_status: none`",
    ):
        assert snippet in text


def test_backlog_protocol_persists_work_kind() -> None:
    text = _read(BACKLOG_PATH)
    for snippet in (
        "**Work kinds válidos aquí:**",
        "- **Work kind:** technical | investigation | expansion",
    ):
        assert snippet in text


def test_opportunities_packet_b_normalization_is_documented() -> None:
    text = _read(OPPORTUNITIES_PATH)
    for snippet in (
        "Ejecutar acquire sobre SOM buscando filings intermedios públicos utilizables.",
        "Ejecutar un experimento de acquire sobre Euronext usando TEP como ticker ancla",
        "Ejecutar un experimento de acquire sobre HKEX usando `0327` como ticker ancla",
        "Ejecutar acquire y verificación de coverage/manifest sobre TALO",
        "Mientras no exista candidato ticker-level",
    ):
        assert snippet in text


def test_capacity_scout_mirrors_share_packet_b_contract() -> None:
    required = (
        "eval --all --output-json /tmp/elsian-capacity-scout/eval_report.json",
        "`pass_summary`",
        "`findings`",
        "`reconciliation_summary`",
        "`partial_pass`",
        "manifest_expected_absent",
        "`investigation_BL_ready`",
        "`expansion_candidate`",
        "`packageable_count`",
        "OP-001",
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
        "investigation_bl_ready_count",
        "expansion_candidate_count",
        "## Resumen ejecutivo",
        "expansion-curation governance-only wave",
    )
    for path in (ORCHESTRATOR_AGENT_PATH, ORCHESTRATOR_SKILL_PATH):
        text = _read(path)
        for snippet in required:
            assert snippet in text, f"{snippet!r} missing in {path}"


def test_director_mirrors_reference_packet_b_batch_rules() -> None:
    required = (
        "max `3` BLs",
        "max `1` `shared-core`",
        "`Work kind`",
        "`investigation_BL_ready`",
        "`expansion_candidate`",
        "`1` expansion BL per batch",
        "baseline-only governance wave",
        "opportunity-normalization wave",
        "expansion-curation governance wave",
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
