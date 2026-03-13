from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from elsian.analyze.discovery_baseline import build_eval_output_payload


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "build_scout_context.py"
SPEC = importlib.util.spec_from_file_location("build_scout_context", MODULE_PATH)
assert SPEC and SPEC.loader
build_scout_context = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_scout_context)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_case(cases_root: Path, ticker: str, *, with_manifest: bool) -> None:
    case_dir = cases_root / ticker
    case_dir.mkdir(parents=True, exist_ok=True)
    _write_json(case_dir / "case.json", {"ticker": ticker, "source_hint": "sec"})
    filings_dir = case_dir / "filings"
    filings_dir.mkdir(exist_ok=True)
    (filings_dir / "SRC_001.txt").write_text(f"{ticker} filing", encoding="utf-8")
    if with_manifest:
        _write_json(case_dir / "filings_manifest.json", {"ticker": ticker, "items": []})


def _write_opportunities(path: Path) -> None:
    path.write_text(
        "# Opportunities\n\n"
        "## Module 1 operational opportunities\n\n"
        "### Near BL-ready\n\n"
        "#### OP-001 — SOM\n"
        "- **Subject type:** ticker\n"
        "- **Subject id:** SOM\n"
        "- **Canonical state:** frontera abierta\n"
        "- **Why it matters:** importa.\n"
        "- **Live evidence:** project state.\n"
        "- **Unknowns remaining:** experimento único.\n"
        "- **Promotion trigger:** evidencia nueva.\n"
        "- **Blast radius if promoted:** targeted\n"
        "- **Expected effort:** bounded\n"
        "- **Last reviewed:** 2026-03-13\n"
        "- **Disposition:** keep\n"
        "\n## Non-operational / future opportunities\n",
        encoding="utf-8",
    )


def _valid_eval_payload() -> dict[str, object]:
    return build_eval_output_payload(
        [
            {
                "ticker": "AAA",
                "total_expected": 1,
                "matched": 0,
                "wrong": 1,
                "missed": 0,
                "extra": 0,
                "score": 0.0,
                "filings_coverage_pct": 100.0,
                "required_fields_coverage_pct": 0.0,
                "readiness_score": 0.0,
                "validator_confidence_score": 100.0,
                "provenance_coverage_pct": 100.0,
                "extra_penalty": 0.0,
            }
        ]
    )


def _valid_diagnose_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "generated_at": "2026-03-13T10:00:00Z",
        "cases_dir": "/tmp/cases",
        "summary": {
            "tickers_analyzed": 1,
            "tickers_with_eval": 1,
            "tickers_skipped": 0,
            "total_expected": 1,
            "total_matched": 1,
            "total_wrong": 0,
            "total_missed": 0,
            "total_extra": 0,
            "overall_score_pct": 100.0,
        },
        "root_cause_summary": {},
        "by_period_type": {},
        "by_field_category": {},
        "hotspots": [],
    }


def test_eval_artifact_valid_means_ok_even_if_content_fails(tmp_path: Path) -> None:
    eval_json = tmp_path / "eval_report.json"
    diagnose_json = tmp_path / "diagnose_report.json"
    cases_root = tmp_path / "cases"
    opportunities_md = tmp_path / "OPPORTUNITIES.md"

    _write_json(eval_json, _valid_eval_payload())
    _write_json(diagnose_json, _valid_diagnose_payload())
    _write_case(cases_root, "AAA", with_manifest=True)
    _write_opportunities(opportunities_md)

    context = build_scout_context.build_scout_context(
        eval_json_path=eval_json,
        diagnose_json_path=diagnose_json,
        cases_root=cases_root,
        opportunities_md_path=opportunities_md,
    )

    assert context["eval_run"]["status"] == "ok"
    assert context["eval_run"]["artifact_path"] == str(eval_json.resolve())
    assert context["eval_run"]["signature"]
    assert context["partial_pass"] is False


def test_context_has_exact_top_level_and_run_shapes(tmp_path: Path) -> None:
    eval_json = tmp_path / "eval_report.json"
    diagnose_json = tmp_path / "diagnose_report.json"
    cases_root = tmp_path / "cases"
    opportunities_md = tmp_path / "OPPORTUNITIES.md"

    _write_json(eval_json, _valid_eval_payload())
    _write_json(diagnose_json, _valid_diagnose_payload())
    _write_case(cases_root, "AAA", with_manifest=True)
    _write_opportunities(opportunities_md)

    context = build_scout_context.build_scout_context(
        eval_json_path=eval_json,
        diagnose_json_path=diagnose_json,
        cases_root=cases_root,
        opportunities_md_path=opportunities_md,
    )

    assert tuple(context.keys()) == (
        "eval_run",
        "diagnose_run",
        "baseline_signatures",
        "case_review",
        "partial_pass",
        "partial_reasons",
    )
    assert tuple(context["eval_run"].keys()) == ("status", "artifact_path", "signature", "notes")
    assert tuple(context["diagnose_run"].keys()) == ("status", "artifact_path", "signature", "notes")
    assert tuple(context["baseline_signatures"].keys()) == (
        "last_eval_signature",
        "last_diagnose_signature",
        "last_cases_signature",
        "last_operational_opportunities_signature",
    )
    assert tuple(context["case_review"].keys()) == (
        "all_cases_reviewed",
        "all_manifests_reviewed",
        "manifest_missing_tickers",
    )
    assert context["eval_run"]["notes"] == ""
    assert context["diagnose_run"]["notes"] == ""
    assert all(context["baseline_signatures"].values())
    assert context["partial_reasons"] == []


def test_eval_missing_or_corrupt_is_unusable_artifact(tmp_path: Path) -> None:
    diagnose_json = tmp_path / "diagnose_report.json"
    cases_root = tmp_path / "cases"
    opportunities_md = tmp_path / "OPPORTUNITIES.md"
    _write_json(diagnose_json, _valid_diagnose_payload())
    _write_case(cases_root, "AAA", with_manifest=True)
    _write_opportunities(opportunities_md)

    missing_context = build_scout_context.build_scout_context(
        eval_json_path=tmp_path / "missing_eval.json",
        diagnose_json_path=diagnose_json,
        cases_root=cases_root,
        opportunities_md_path=opportunities_md,
    )
    assert missing_context["eval_run"]["status"] == "unusable_artifact"
    assert missing_context["partial_pass"] is True

    corrupt_eval = tmp_path / "corrupt_eval.json"
    corrupt_eval.write_text("{not-json", encoding="utf-8")
    corrupt_context = build_scout_context.build_scout_context(
        eval_json_path=corrupt_eval,
        diagnose_json_path=diagnose_json,
        cases_root=cases_root,
        opportunities_md_path=opportunities_md,
    )
    assert corrupt_context["eval_run"]["status"] == "unusable_artifact"
    assert corrupt_context["partial_pass"] is True


def test_diagnose_valid_and_signable_means_ok(tmp_path: Path) -> None:
    eval_json = tmp_path / "eval_report.json"
    diagnose_json = tmp_path / "diagnose_report.json"
    cases_root = tmp_path / "cases"
    opportunities_md = tmp_path / "OPPORTUNITIES.md"

    _write_json(eval_json, _valid_eval_payload())
    _write_json(diagnose_json, _valid_diagnose_payload())
    _write_case(cases_root, "AAA", with_manifest=True)
    _write_opportunities(opportunities_md)

    context = build_scout_context.build_scout_context(
        eval_json_path=eval_json,
        diagnose_json_path=diagnose_json,
        cases_root=cases_root,
        opportunities_md_path=opportunities_md,
    )

    assert context["diagnose_run"]["status"] == "ok"
    assert context["diagnose_run"]["artifact_path"] == str(diagnose_json.resolve())
    assert context["diagnose_run"]["signature"]
    assert context["partial_pass"] is False


def test_diagnose_existing_but_not_signable_is_unusable_artifact(tmp_path: Path) -> None:
    eval_json = tmp_path / "eval_report.json"
    diagnose_json = tmp_path / "diagnose_report.json"
    cases_root = tmp_path / "cases"
    opportunities_md = tmp_path / "OPPORTUNITIES.md"

    _write_json(eval_json, _valid_eval_payload())
    _write_json(diagnose_json, {"summary": {}})
    _write_case(cases_root, "AAA", with_manifest=True)
    _write_opportunities(opportunities_md)

    context = build_scout_context.build_scout_context(
        eval_json_path=eval_json,
        diagnose_json_path=diagnose_json,
        cases_root=cases_root,
        opportunities_md_path=opportunities_md,
    )

    assert context["diagnose_run"]["status"] == "unusable_artifact"
    assert context["diagnose_run"]["artifact_path"] is None
    assert context["diagnose_run"]["signature"] is None
    assert context["partial_pass"] is True


def test_manifest_missing_tickers_detects_0327_talo_tep(tmp_path: Path) -> None:
    eval_json = tmp_path / "eval_report.json"
    diagnose_json = tmp_path / "diagnose_report.json"
    cases_root = tmp_path / "cases"
    opportunities_md = tmp_path / "OPPORTUNITIES.md"

    _write_json(eval_json, _valid_eval_payload())
    _write_json(diagnose_json, _valid_diagnose_payload())
    _write_case(cases_root, "0327", with_manifest=False)
    _write_case(cases_root, "TALO", with_manifest=False)
    _write_case(cases_root, "TEP", with_manifest=False)
    _write_case(cases_root, "TZOO", with_manifest=True)
    _write_case(cases_root, "NVDA", with_manifest=True)
    _write_opportunities(opportunities_md)

    context = build_scout_context.build_scout_context(
        eval_json_path=eval_json,
        diagnose_json_path=diagnose_json,
        cases_root=cases_root,
        opportunities_md_path=opportunities_md,
    )

    assert context["case_review"]["all_cases_reviewed"] is True
    assert context["case_review"]["all_manifests_reviewed"] is True
    assert context["case_review"]["manifest_missing_tickers"] == ["0327", "TALO", "TEP"]
