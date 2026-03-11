"""tests/unit/test_scaffold.py — unit tests for elsian.scaffold.

Tests build_task_seed and build_case_seed using only in-memory calls
(no file I/O, no tmp_path required).  Tests for write_* functions use
tmp_path fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from elsian.scaffold import (
    PERIOD_SCOPES,
    TASK_KINDS,
    VALIDATION_TIERS,
    build_case_seed,
    build_task_seed,
    write_case_seed,
    write_task_seed,
)


# ---------------------------------------------------------------------------
# build_task_seed — valid inputs
# ---------------------------------------------------------------------------


class TestBuildTaskSeedValid:
    def _defaults(self) -> dict:
        return dict(
            task_id="BL-999",
            title="Test task",
            kind="technical",
            validation_tier="targeted",
            write_set=["elsian/cli.py"],
            risks=["Risk A"],
            validation_plan="Run pytest -q on targeted tests.",
            acceptance_criteria="All targeted tests pass.",
        )

    def test_returns_tuple_manifest_and_notes(self) -> None:
        manifest, notes_md = build_task_seed(**self._defaults())
        assert isinstance(manifest, dict)
        assert isinstance(notes_md, str)

    def test_manifest_required_keys_present(self) -> None:
        manifest, _ = build_task_seed(**self._defaults())
        for key in ("task_id", "title", "kind", "validation_tier", "claimed_bl_status", "write_set", "notes"):
            assert key in manifest, f"missing key: {key}"

    def test_manifest_claimed_bl_status_is_none(self) -> None:
        manifest, _ = build_task_seed(**self._defaults())
        assert manifest["claimed_bl_status"] == "none"

    def test_manifest_is_json_serializable(self) -> None:
        manifest, _ = build_task_seed(**self._defaults())
        # Should not raise
        json.dumps(manifest)

    def test_risks_embedded_in_notes(self) -> None:
        d = self._defaults()
        d["risks"] = ["Risk X", "Risk Y"]
        manifest, _ = build_task_seed(**d)
        assert "Risk X" in manifest["notes"]
        assert "Risk Y" in manifest["notes"]

    def test_validation_plan_embedded_in_notes(self) -> None:
        manifest, _ = build_task_seed(**self._defaults())
        assert "Run pytest -q on targeted tests." in manifest["notes"]

    def test_acceptance_criteria_embedded_in_notes(self) -> None:
        manifest, _ = build_task_seed(**self._defaults())
        assert "All targeted tests pass." in manifest["notes"]

    def test_extra_notes_prepended(self) -> None:
        d = self._defaults()
        d["notes"] = "Extra context."
        manifest, _ = build_task_seed(**d)
        assert manifest["notes"].startswith("Extra context.")

    def test_notes_md_contains_task_id(self) -> None:
        _, notes_md = build_task_seed(**self._defaults())
        assert "BL-999" in notes_md

    def test_notes_md_contains_risks_section(self) -> None:
        d = self._defaults()
        d["risks"] = ["Critical risk here"]
        _, notes_md = build_task_seed(**d)
        assert "## Risks" in notes_md
        assert "Critical risk here" in notes_md

    def test_notes_md_contains_validation_section(self) -> None:
        _, notes_md = build_task_seed(**self._defaults())
        assert "## Validation Plan" in notes_md

    def test_notes_md_contains_acceptance_section(self) -> None:
        _, notes_md = build_task_seed(**self._defaults())
        assert "## Acceptance Criteria" in notes_md

    def test_notes_md_contains_write_set_section(self) -> None:
        d = self._defaults()
        d["write_set"] = ["elsian/cli.py", "elsian/scaffold.py"]
        _, notes_md = build_task_seed(**d)
        assert "## Write Set" in notes_md
        assert "elsian/cli.py" in notes_md
        assert "elsian/scaffold.py" in notes_md

    def test_references_optional(self) -> None:
        d = self._defaults()
        d["references"] = ["BL-061"]
        manifest, _ = build_task_seed(**d)
        assert manifest["references"] == ["BL-061"]

    def test_no_references_key_when_omitted(self) -> None:
        manifest, _ = build_task_seed(**self._defaults())
        assert "references" not in manifest

    def test_blocked_surfaces_optional(self) -> None:
        d = self._defaults()
        d["blocked_surfaces"] = ["elsian/acquire/"]
        manifest, _ = build_task_seed(**d)
        assert manifest["blocked_surfaces"] == ["elsian/acquire/"]

    def test_expected_governance_updates_list(self) -> None:
        d = self._defaults()
        d["expected_governance_updates"] = ["CHANGELOG.md"]
        manifest, _ = build_task_seed(**d)
        assert manifest["expected_governance_updates"] == ["CHANGELOG.md"]

    def test_expected_governance_updates_none_literal(self) -> None:
        d = self._defaults()
        d["expected_governance_updates"] = "none"
        manifest, _ = build_task_seed(**d)
        assert manifest["expected_governance_updates"] == "none"

    @pytest.mark.parametrize("kind", TASK_KINDS)
    def test_all_kinds_accepted(self, kind: str) -> None:
        d = self._defaults()
        d["kind"] = kind
        manifest, _ = build_task_seed(**d)
        assert manifest["kind"] == kind

    @pytest.mark.parametrize("tier", VALIDATION_TIERS)
    def test_all_validation_tiers_accepted(self, tier: str) -> None:
        d = self._defaults()
        d["validation_tier"] = tier
        manifest, _ = build_task_seed(**d)
        assert manifest["validation_tier"] == tier


# ---------------------------------------------------------------------------
# build_task_seed — invalid inputs (enforcement contract)
# ---------------------------------------------------------------------------


class TestBuildTaskSeedEnforcement:
    def _defaults(self) -> dict:
        return dict(
            task_id="BL-999",
            title="Test task",
            kind="technical",
            validation_tier="targeted",
            write_set=["elsian/cli.py"],
            risks=["Risk A"],
            validation_plan="Run tests.",
            acceptance_criteria="Tests pass.",
        )

    def test_empty_task_id_raises(self) -> None:
        d = self._defaults()
        d["task_id"] = ""
        with pytest.raises(ValueError, match="task_id"):
            build_task_seed(**d)

    def test_blank_task_id_raises(self) -> None:
        d = self._defaults()
        d["task_id"] = "   "
        with pytest.raises(ValueError, match="task_id"):
            build_task_seed(**d)

    def test_empty_title_raises(self) -> None:
        d = self._defaults()
        d["title"] = ""
        with pytest.raises(ValueError, match="title"):
            build_task_seed(**d)

    def test_invalid_kind_raises(self) -> None:
        d = self._defaults()
        d["kind"] = "invalid"
        with pytest.raises(ValueError, match="kind"):
            build_task_seed(**d)

    def test_invalid_validation_tier_raises(self) -> None:
        d = self._defaults()
        d["validation_tier"] = "unknown"
        with pytest.raises(ValueError, match="validation_tier"):
            build_task_seed(**d)

    def test_empty_write_set_raises(self) -> None:
        d = self._defaults()
        d["write_set"] = []
        with pytest.raises(ValueError, match="write_set"):
            build_task_seed(**d)

    def test_empty_risks_raises(self) -> None:
        d = self._defaults()
        d["risks"] = []
        with pytest.raises(ValueError, match="risks"):
            build_task_seed(**d)

    def test_blank_validation_plan_raises(self) -> None:
        d = self._defaults()
        d["validation_plan"] = "   "
        with pytest.raises(ValueError, match="validation_plan"):
            build_task_seed(**d)

    def test_empty_acceptance_criteria_raises(self) -> None:
        d = self._defaults()
        d["acceptance_criteria"] = ""
        with pytest.raises(ValueError, match="acceptance_criteria"):
            build_task_seed(**d)


# ---------------------------------------------------------------------------
# write_task_seed — disk I/O
# ---------------------------------------------------------------------------


class TestWriteTaskSeed:
    def _defaults(self) -> dict:
        return dict(
            task_id="BL-TEST",
            title="Test scaffold task",
            kind="technical",
            validation_tier="targeted",
            write_set=["elsian/scaffold.py"],
            risks=["Scope creep"],
            validation_plan="pytest -q targeted",
            acceptance_criteria="All tests green.",
        )

    def test_writes_manifest_and_notes_to_output_dir(self, tmp_path: Path) -> None:
        manifest_path, notes_path = write_task_seed(
            **self._defaults(), output_dir=tmp_path
        )
        assert manifest_path.exists()
        assert notes_path.exists()

    def test_manifest_filename_convention(self, tmp_path: Path) -> None:
        manifest_path, _ = write_task_seed(**self._defaults(), output_dir=tmp_path)
        assert manifest_path.name == "BL-TEST.task_manifest.json"

    def test_notes_filename_convention(self, tmp_path: Path) -> None:
        _, notes_path = write_task_seed(**self._defaults(), output_dir=tmp_path)
        assert notes_path.name == "BL-TEST.task_notes.md"

    def test_manifest_is_valid_json(self, tmp_path: Path) -> None:
        manifest_path, _ = write_task_seed(**self._defaults(), output_dir=tmp_path)
        data = json.loads(manifest_path.read_text("utf-8"))
        assert data["task_id"] == "BL-TEST"

    def test_raises_on_existing_manifest_without_force(self, tmp_path: Path) -> None:
        write_task_seed(**self._defaults(), output_dir=tmp_path)
        with pytest.raises(FileExistsError):
            write_task_seed(**self._defaults(), output_dir=tmp_path)

    def test_force_overwrites_existing(self, tmp_path: Path) -> None:
        write_task_seed(**self._defaults(), output_dir=tmp_path)
        d = self._defaults()
        d["title"] = "Updated title"
        manifest_path, _ = write_task_seed(**d, output_dir=tmp_path, force=True)
        data = json.loads(manifest_path.read_text("utf-8"))
        assert data["title"] == "Updated title"

    def test_creates_output_dir_if_missing(self, tmp_path: Path) -> None:
        nested = tmp_path / "nested" / "dir"
        write_task_seed(**self._defaults(), output_dir=nested)
        assert nested.exists()


# ---------------------------------------------------------------------------
# build_case_seed — valid inputs
# ---------------------------------------------------------------------------


class TestBuildCaseSeedValid:
    def _defaults(self) -> dict:
        return dict(
            ticker="TEST",
            source_hint="sec",
            currency="usd",
        )

    def test_returns_tuple_case_and_notes(self) -> None:
        case, notes_md = build_case_seed(**self._defaults())
        assert isinstance(case, dict)
        assert isinstance(notes_md, str)

    def test_ticker_uppercased(self) -> None:
        case, _ = build_case_seed(**self._defaults())
        assert case["ticker"] == "TEST"

    def test_ticker_normalised_from_lowercase(self) -> None:
        case, _ = build_case_seed(ticker="lower", source_hint="sec", currency="usd")
        assert case["ticker"] == "LOWER"

    def test_currency_uppercased(self) -> None:
        case, _ = build_case_seed(**self._defaults())
        assert case["currency"] == "USD"

    def test_source_hint_lowercased(self) -> None:
        case, _ = build_case_seed(ticker="T", source_hint="SEC", currency="USD")
        assert case["source_hint"] == "sec"

    def test_default_period_scope_annual_only(self) -> None:
        case, _ = build_case_seed(**self._defaults())
        assert case["period_scope"] == "ANNUAL_ONLY"

    def test_full_period_scope_accepted(self) -> None:
        case, _ = build_case_seed(**self._defaults(), period_scope="FULL")
        assert case["period_scope"] == "FULL"

    def test_required_keys_for_contract(self) -> None:
        case, _ = build_case_seed(**self._defaults())
        for key in ("ticker", "currency", "source_hint", "period_scope"):
            assert key in case

    def test_exchange_optional(self) -> None:
        case, _ = build_case_seed(**self._defaults(), exchange="NASDAQ")
        assert case["exchange"] == "NASDAQ"

    def test_country_optional(self) -> None:
        case, _ = build_case_seed(**self._defaults(), country="US")
        assert case["country"] == "US"

    def test_cik_optional(self) -> None:
        case, _ = build_case_seed(**self._defaults(), cik="0001234567")
        assert case["cik"] == "0001234567"

    def test_fiscal_year_end_month_optional(self) -> None:
        case, _ = build_case_seed(**self._defaults(), fiscal_year_end_month=6)
        assert case["fiscal_year_end_month"] == 6

    def test_no_fiscal_year_end_month_key_when_omitted(self) -> None:
        case, _ = build_case_seed(**self._defaults())
        assert "fiscal_year_end_month" not in case

    def test_notes_md_contains_ticker(self) -> None:
        _, notes_md = build_case_seed(**self._defaults())
        assert "TEST" in notes_md

    def test_notes_md_contains_risks_section(self) -> None:
        _, notes_md = build_case_seed(**self._defaults())
        assert "## Risks" in notes_md

    def test_notes_md_contains_acceptance_criteria_section(self) -> None:
        _, notes_md = build_case_seed(**self._defaults())
        assert "## Acceptance Criteria" in notes_md

    def test_notes_md_contains_todo_section(self) -> None:
        _, notes_md = build_case_seed(**self._defaults())
        assert "## TODO before acquire" in notes_md

    def test_notes_md_contains_source_notes_section(self) -> None:
        _, notes_md = build_case_seed(**self._defaults())
        assert "## Source Notes" in notes_md

    def test_custom_notes_stored(self) -> None:
        case, _ = build_case_seed(**self._defaults(), notes="custom note")
        assert "custom note" in case["notes"]

    @pytest.mark.parametrize("scope", PERIOD_SCOPES)
    def test_all_period_scopes_accepted(self, scope: str) -> None:
        case, _ = build_case_seed(**self._defaults(), period_scope=scope)
        assert case["period_scope"] == scope


# ---------------------------------------------------------------------------
# build_case_seed — invalid inputs (enforcement)
# ---------------------------------------------------------------------------


class TestBuildCaseSeedEnforcement:
    def _defaults(self) -> dict:
        return dict(ticker="T", source_hint="sec", currency="USD")

    def test_empty_ticker_raises(self) -> None:
        with pytest.raises(ValueError, match="ticker"):
            build_case_seed(ticker="", source_hint="sec", currency="USD")

    def test_blank_source_hint_raises(self) -> None:
        with pytest.raises(ValueError, match="source_hint"):
            build_case_seed(ticker="T", source_hint="  ", currency="USD")

    def test_empty_currency_raises(self) -> None:
        with pytest.raises(ValueError, match="currency"):
            build_case_seed(ticker="T", source_hint="sec", currency="")

    def test_invalid_period_scope_raises(self) -> None:
        with pytest.raises(ValueError, match="period_scope"):
            build_case_seed(**self._defaults(), period_scope="QUARTERLY")


# ---------------------------------------------------------------------------
# write_case_seed — disk I/O
# ---------------------------------------------------------------------------


class TestWriteCaseSeed:
    def _defaults(self) -> dict:
        return dict(
            ticker="NEWCO",
            source_hint="sec",
            currency="USD",
        )

    def test_writes_case_json_and_case_notes(self, tmp_path: Path) -> None:
        case_path, notes_path = write_case_seed(
            **self._defaults(), output_dir=tmp_path
        )
        assert case_path.exists()
        assert notes_path.exists()

    def test_case_json_filename(self, tmp_path: Path) -> None:
        case_path, _ = write_case_seed(**self._defaults(), output_dir=tmp_path)
        assert case_path.name == "case.json"

    def test_case_notes_filename(self, tmp_path: Path) -> None:
        _, notes_path = write_case_seed(**self._defaults(), output_dir=tmp_path)
        assert notes_path.name == "CASE_NOTES.md"

    def test_case_dir_created_under_ticker_upper(self, tmp_path: Path) -> None:
        write_case_seed(ticker="newco", source_hint="sec", currency="USD", output_dir=tmp_path)
        assert (tmp_path / "NEWCO" / "case.json").exists()

    def test_case_json_is_valid_json(self, tmp_path: Path) -> None:
        case_path, _ = write_case_seed(**self._defaults(), output_dir=tmp_path)
        data = json.loads(case_path.read_text("utf-8"))
        assert data["ticker"] == "NEWCO"
        assert data["source_hint"] == "sec"
        assert data["currency"] == "USD"

    def test_raises_on_existing_case_json_without_force(self, tmp_path: Path) -> None:
        write_case_seed(**self._defaults(), output_dir=tmp_path)
        with pytest.raises(FileExistsError):
            write_case_seed(**self._defaults(), output_dir=tmp_path)

    def test_force_overwrites_existing(self, tmp_path: Path) -> None:
        write_case_seed(**self._defaults(), output_dir=tmp_path)
        d = self._defaults()
        d["currency"] = "EUR"
        case_path, _ = write_case_seed(**d, output_dir=tmp_path, force=True)
        data = json.loads(case_path.read_text("utf-8"))
        assert data["currency"] == "EUR"

    def test_case_notes_contains_acceptance_criteria(self, tmp_path: Path) -> None:
        _, notes_path = write_case_seed(**self._defaults(), output_dir=tmp_path)
        content = notes_path.read_text("utf-8")
        assert "Acceptance Criteria" in content

    def test_case_notes_contains_risks(self, tmp_path: Path) -> None:
        _, notes_path = write_case_seed(**self._defaults(), output_dir=tmp_path)
        content = notes_path.read_text("utf-8")
        assert "Risks" in content
