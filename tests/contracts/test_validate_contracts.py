from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "validate_contracts.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_contracts", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Existing passing tests
# ---------------------------------------------------------------------------


def test_validate_all_contracts_passes_for_tracked_repo_artifacts():
    module = _load_module()

    issues = module.validate_all_contracts()

    assert issues == {}


def test_validate_task_manifest_contract_accepts_minimal_sample(tmp_path: Path):
    module = _load_module()
    manifest_path = tmp_path / "task_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "task_id": "BL-059",
                "title": "Contratos versionados",
                "kind": "technical",
                "validation_tier": "shared-core",
                "claimed_bl_status": "none",
                "write_set": [
                    "schemas/v1/case.schema.json",
                    "scripts/validate_contracts.py",
                ],
                "references": ["BL-059"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    issues = module.validate_single_contract("task_manifest", manifest_path)

    assert issues == []


def test_curate_prompt_contract_is_current():
    module = _load_module()

    issues = module.validate_curate_prompt_contract()

    assert issues == []


# ---------------------------------------------------------------------------
# BL-059: canonical set alignment
# ---------------------------------------------------------------------------


def test_canonical_alignment_passes_for_repo():
    """Invariant (a): all three sources agree for the live repo."""
    module = _load_module()
    issues = module.validate_canonical_set_alignment()
    assert issues == []


def test_canonical_drift_schema_vs_aliases_detected():
    """_check_canonical_drift reports fields missing from field_aliases.json."""
    module = _load_module()
    schema_enum = {"field_a", "field_b", "field_c"}
    aliases_keys = {"field_a", "field_c"}  # missing field_b
    validation_canon = {"field_a", "field_b", "field_c"}

    issues = module._check_canonical_drift(schema_enum, aliases_keys, validation_canon)

    assert any("field_b" in i and "field_aliases.json" in i for i in issues)


def test_canonical_drift_schema_vs_validation_detected():
    """_check_canonical_drift reports fields missing from _CANONICAL_FIELDS."""
    module = _load_module()
    schema_enum = {"field_a", "field_b"}
    aliases_keys = {"field_a", "field_b"}
    validation_canon = {"field_a"}  # missing field_b

    issues = module._check_canonical_drift(schema_enum, aliases_keys, validation_canon)

    assert any("field_b" in i and "_CANONICAL_FIELDS" in i for i in issues)


def test_canonical_drift_extra_in_aliases_detected():
    """_check_canonical_drift reports extra fields in field_aliases.json not in schema."""
    module = _load_module()
    schema_enum = {"field_a"}
    aliases_keys = {"field_a", "field_extra"}  # extra not in schema
    validation_canon = {"field_a"}

    issues = module._check_canonical_drift(schema_enum, aliases_keys, validation_canon)

    assert any("field_extra" in i and "field_aliases.json" in i for i in issues)


# ---------------------------------------------------------------------------
# BL-059: curate prompt legacy markers
# ---------------------------------------------------------------------------


def test_curate_prompt_text_detects_legacy_22_campos():
    """_check_curate_prompt_text flags 'Los 22 campos canónicos' as legacy."""
    module = _load_module()
    text = "Los 22 campos canónicos son importantes.\n"

    issues = module._check_curate_prompt_text(text, "<test>")

    assert any("Los 22 campos canónicos" in i for i in issues)


def test_curate_prompt_text_detects_missing_required_29_campos():
    """_check_curate_prompt_text flags missing '29 campos canónicos'."""
    module = _load_module()
    # Text with none of the required markers
    text = "Un prompt sin los marcadores requeridos."

    issues = module._check_curate_prompt_text(text, "<test>")

    assert any("29 campos canónicos" in i for i in issues)


# ---------------------------------------------------------------------------
# BL-059: cross-case consistency
# ---------------------------------------------------------------------------


def test_cross_case_consistency_passes_for_tracked_cases():
    """Invariant (b): all tracked tickers are internally consistent."""
    module = _load_module()
    issues = module.validate_cross_case_consistency()
    assert issues == []


def test_cross_case_ticker_mismatch_detected():
    """_check_cross_ticker_data detects ticker mismatch between case.json and expected.json."""
    module = _load_module()
    case_data = {"ticker": "FOO", "currency": "USD", "period_scope": "ANNUAL_ONLY"}
    expected_data = {"ticker": "BAR", "currency": "USD"}

    issues = module._check_cross_ticker_data("FOO", case_data, expected_data)

    assert any("ticker mismatch" in i for i in issues)


def test_cross_case_currency_mismatch_detected():
    """_check_cross_ticker_data detects currency mismatch."""
    module = _load_module()
    case_data = {"ticker": "FOO", "currency": "USD", "period_scope": "ANNUAL_ONLY"}
    expected_data = {"ticker": "FOO", "currency": "EUR"}

    issues = module._check_cross_ticker_data("FOO", case_data, expected_data)

    assert any("currency mismatch" in i for i in issues)


def test_cross_case_period_scope_mismatch_detected():
    """_check_cross_ticker_data detects period_scope mismatch when expected.json declares one."""
    module = _load_module()
    case_data = {"ticker": "FOO", "currency": "USD", "period_scope": "ANNUAL_ONLY"}
    expected_data = {"ticker": "FOO", "currency": "USD", "period_scope": "FULL"}

    issues = module._check_cross_ticker_data("FOO", case_data, expected_data)

    assert any("period_scope mismatch" in i for i in issues)


def test_cross_case_period_scope_absent_in_expected_not_flagged():
    """No mismatch when expected.json omits period_scope (common pattern)."""
    module = _load_module()
    case_data = {"ticker": "FOO", "currency": "USD", "period_scope": "ANNUAL_ONLY"}
    expected_data = {"ticker": "FOO", "currency": "USD"}  # no period_scope

    issues = module._check_cross_ticker_data("FOO", case_data, expected_data)

    assert not any("period_scope" in i for i in issues)


def test_cross_case_derived_artifact_ticker_mismatch_detected():
    """_check_cross_ticker_data detects ticker mismatch in a tracked derived artifact."""
    module = _load_module()
    case_data = {"ticker": "FOO", "currency": "USD", "period_scope": "ANNUAL_ONLY"}
    expected_data = {"ticker": "FOO", "currency": "USD"}
    derived = [("truth_pack.json", {"ticker": "BAR"})]

    issues = module._check_cross_ticker_data("FOO", case_data, expected_data, derived)

    assert any("truth_pack.json" in i and "ticker mismatch" in i for i in issues)


# ---------------------------------------------------------------------------
# BL-059: task_manifest contract still enforces schema (regression)
# ---------------------------------------------------------------------------


def test_validate_task_manifest_contract_rejects_invalid_kind():
    """task_manifest validator rejects unknown kind value."""
    module = _load_module()
    invalid_data = {
        "task_id": "BL-059",
        "title": "Bad manifest",
        "kind": "INVALID_KIND",
        "validation_tier": "targeted",
        "claimed_bl_status": "none",
        "write_set": ["scripts/validate_contracts.py"],
    }
    with tempfile.NamedTemporaryFile(
        suffix=".json", mode="w", encoding="utf-8", delete=False
    ) as f:
        json.dump(invalid_data, f)
        tmp_path = Path(f.name)

    issues = module.validate_single_contract("task_manifest", tmp_path)
    tmp_path.unlink(missing_ok=True)

    assert any("kind" in i for i in issues)


# ---------------------------------------------------------------------------
# BL-059 auditor-fix: derived artifact currency / metadata.period_scope checks
# ---------------------------------------------------------------------------


def test_cross_case_derived_extraction_result_currency_mismatch_detected():
    """_check_cross_ticker_data detects currency mismatch in a tracked extraction_result."""
    module = _load_module()
    case_data = {"ticker": "FOO", "currency": "USD", "period_scope": "ANNUAL_ONLY"}
    expected_data = {"ticker": "FOO", "currency": "USD"}
    derived = [("extraction_result.json", {"ticker": "FOO", "currency": "EUR"})]

    issues = module._check_cross_ticker_data("FOO", case_data, expected_data, derived)

    assert any("extraction_result.json" in i and "currency mismatch" in i for i in issues)


def test_cross_case_derived_truth_pack_currency_mismatch_detected():
    """_check_cross_ticker_data detects currency mismatch in a tracked truth_pack."""
    module = _load_module()
    case_data = {"ticker": "FOO", "currency": "USD", "period_scope": "ANNUAL_ONLY"}
    expected_data = {"ticker": "FOO", "currency": "USD"}
    derived = [("truth_pack.json", {"ticker": "FOO", "currency": "EUR"})]

    issues = module._check_cross_ticker_data("FOO", case_data, expected_data, derived)

    assert any("truth_pack.json" in i and "currency mismatch" in i for i in issues)


def test_cross_case_derived_truth_pack_period_scope_mismatch_detected():
    """_check_cross_ticker_data detects metadata.period_scope mismatch in a tracked truth_pack."""
    module = _load_module()
    case_data = {"ticker": "FOO", "currency": "USD", "period_scope": "ANNUAL_ONLY"}
    expected_data = {"ticker": "FOO", "currency": "USD"}
    derived = [("truth_pack.json", {"ticker": "FOO", "currency": "USD", "metadata": {"period_scope": "FULL"}})]

    issues = module._check_cross_ticker_data("FOO", case_data, expected_data, derived)

    assert any("truth_pack.json" in i and "metadata.period_scope mismatch" in i for i in issues)


def test_cross_case_derived_no_currency_key_not_flagged():
    """No currency flag when a derived artifact doesn't expose currency (e.g. filings_manifest)."""
    module = _load_module()
    case_data = {"ticker": "FOO", "currency": "USD", "period_scope": "ANNUAL_ONLY"}
    expected_data = {"ticker": "FOO", "currency": "USD"}
    derived = [("filings_manifest.json", {"ticker": "FOO"})]  # no currency key

    issues = module._check_cross_ticker_data("FOO", case_data, expected_data, derived)

    assert not any("currency" in i for i in issues)


def test_cross_case_derived_truth_pack_no_period_scope_in_metadata_not_flagged():
    """No period_scope flag when truth_pack metadata exists but omits period_scope."""
    module = _load_module()
    case_data = {"ticker": "FOO", "currency": "USD", "period_scope": "ANNUAL_ONLY"}
    expected_data = {"ticker": "FOO", "currency": "USD"}
    # metadata present but without period_scope key
    derived = [("truth_pack.json", {"ticker": "FOO", "currency": "USD", "metadata": {"total_periods": 4}})]

    issues = module._check_cross_ticker_data("FOO", case_data, expected_data, derived)

    assert not any("period_scope" in i for i in issues)
