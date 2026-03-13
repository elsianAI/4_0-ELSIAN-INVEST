from __future__ import annotations

import json
from pathlib import Path

from elsian.analyze.discovery_baseline import (
    build_cases_signature_payload,
    build_eval_output_payload,
    compute_cases_signature,
    compute_diagnose_signature,
    compute_eval_signature,
    compute_operational_opportunities_signature,
    extract_operational_opportunities_subtree,
    parse_discovery_baseline_block,
    validate_eval_output_payload,
)
from elsian.models.result import EvalReport


def test_parse_discovery_baseline_block_absent_is_valid() -> None:
    parsed = parse_discovery_baseline_block("# Project State\n\n## Other\n")
    assert parsed == {
        "present": False,
        "valid": True,
        "values": None,
        "violations": [],
    }


def test_parse_discovery_baseline_block_rejects_wrong_order() -> None:
    parsed = parse_discovery_baseline_block(
        "# Project State\n\n"
        "## Discovery Baseline\n"
        "- last_scout_head: " + ("a" * 40) + "\n"
        "- last_scout_pass_at: 2026-03-13T10:20:30Z\n"
        "- last_eval_signature: " + ("b" * 64) + "\n"
        "- last_diagnose_signature: " + ("c" * 64) + "\n"
        "- last_cases_signature: " + ("d" * 64) + "\n"
        "- last_operational_opportunities_signature: " + ("e" * 64) + "\n"
    )
    assert parsed["present"] is True
    assert parsed["valid"] is False
    assert "project_state_discovery_baseline_field_order" in parsed["violations"]


def test_build_eval_output_payload_orders_reports_by_ticker() -> None:
    payload = build_eval_output_payload(
        [
            EvalReport(ticker="ZZZ", total_expected=1, matched=1, score=100.0),
            EvalReport(ticker="AAA", total_expected=1, matched=1, score=100.0),
        ]
    )
    assert payload["schema_version"] == 1
    assert [report["ticker"] for report in payload["reports"]] == ["AAA", "ZZZ"]
    assert validate_eval_output_payload(payload) == []


def test_compute_eval_signature_ignores_input_order() -> None:
    a = EvalReport(ticker="AAA", total_expected=1, matched=1, score=100.0)
    z = EvalReport(ticker="ZZZ", total_expected=1, matched=1, score=95.0)
    assert compute_eval_signature([a, z]) == compute_eval_signature([z, a])


def test_compute_diagnose_signature_ignores_generated_at_and_cases_dir() -> None:
    base_report = {
        "schema_version": "diagnose_v1",
        "generated_at": "2026-03-13T10:00:00Z",
        "cases_dir": "/tmp/cases-a",
        "summary": {"tickers_with_eval": 2, "overall_score_pct": 99.5},
        "root_cause_summary": {"scale_1k": 3},
        "by_period_type": {"FY": {"wrong": 3}},
        "by_field_category": {"cash_flow": {"wrong": 3}},
        "hotspots": [
            {
                "rank": 1,
                "field": "depreciation_amortization",
                "field_category": "cash_flow",
                "gap_type": "wrong",
                "occurrences": 3,
                "affected_tickers": ["AAA", "ZZZ"],
                "evidence": ["1000x drift"],
                "root_cause_hint": "scale_1k",
                "ignored_field": "not_in_signature",
            }
        ],
    }
    changed_ignored = {
        **base_report,
        "generated_at": "2026-03-14T11:00:00Z",
        "cases_dir": "/tmp/cases-b",
        "hotspots": [{**base_report["hotspots"][0], "ignored_field": "still ignored"}],
    }
    changed_material = {
        **base_report,
        "hotspots": [{**base_report["hotspots"][0], "occurrences": 4}],
    }

    assert compute_diagnose_signature(base_report) == compute_diagnose_signature(changed_ignored)
    assert compute_diagnose_signature(base_report) != compute_diagnose_signature(changed_material)


def test_compute_cases_signature_changes_when_case_json_changes(tmp_path: Path) -> None:
    case_dir = tmp_path / "AAA"
    case_dir.mkdir()
    (case_dir / "case.json").write_text(
        json.dumps({"ticker": "AAA", "source_hint": "sec"}),
        encoding="utf-8",
    )

    first = compute_cases_signature(tmp_path)
    (case_dir / "case.json").write_text(
        json.dumps({"ticker": "AAA", "source_hint": "eu_manual"}),
        encoding="utf-8",
    )
    second = compute_cases_signature(tmp_path)

    assert first != second


def test_compute_cases_signature_changes_when_manifest_changes(tmp_path: Path) -> None:
    case_dir = tmp_path / "AAA"
    case_dir.mkdir()
    (case_dir / "case.json").write_text(
        json.dumps({"ticker": "AAA", "source_hint": "sec"}),
        encoding="utf-8",
    )
    manifest_path = case_dir / "filings_manifest.json"
    manifest_path.write_text(json.dumps({"filings_downloaded": 1}), encoding="utf-8")

    first = compute_cases_signature(tmp_path)
    manifest_path.write_text(json.dumps({"filings_downloaded": 2}), encoding="utf-8")
    second = compute_cases_signature(tmp_path)

    assert first != second


def test_compute_cases_signature_uses_filings_inventory_when_manifest_absent(tmp_path: Path) -> None:
    case_dir = tmp_path / "AAA"
    filings_dir = case_dir / "filings"
    filings_dir.mkdir(parents=True)
    (case_dir / "case.json").write_text(
        json.dumps({"ticker": "AAA", "source_hint": "sec"}),
        encoding="utf-8",
    )
    filing_path = filings_dir / "SRC_001.txt"
    filing_path.write_text("first version", encoding="utf-8")

    payload = build_cases_signature_payload(tmp_path)
    assert payload[0]["filings_inventory"][0]["relative_path"] == "SRC_001.txt"

    first = compute_cases_signature(tmp_path)
    filing_path.write_text("second version", encoding="utf-8")
    second = compute_cases_signature(tmp_path)

    assert first != second


def test_operational_opportunities_signature_uses_only_operational_subtree() -> None:
    markdown = (
        "# Opportunities\n\n"
        "## Module 1 operational opportunities\n\n"
        "### Near BL-ready\n\n"
        "#### OP-001 — SOM\n"
        "- **Subject type:** ticker\n"
        "- **Subject id:** SOM\n\n"
        "## Non-operational / future opportunities\n\n"
        "- Future A\n"
    )
    same_operational = markdown.replace("- Future A", "- Future B")
    changed_operational = markdown.replace("SOM", "TALO", 1)

    assert extract_operational_opportunities_subtree(markdown).startswith(
        "## Module 1 operational opportunities"
    )
    assert compute_operational_opportunities_signature(markdown) == compute_operational_opportunities_signature(
        same_operational
    )
    assert compute_operational_opportunities_signature(markdown) != compute_operational_opportunities_signature(
        changed_operational
    )
