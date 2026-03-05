"""Tests for Level 2 provenance propagation through the pipeline.

BL-006: Every FieldResult must carry complete provenance metadata so that
any extracted value can be traced back to its source filing and table cell.
"""

from __future__ import annotations

import json
import pathlib
import unittest

from elsian.models.field import FieldResult, Provenance


class TestProvenanceModel(unittest.TestCase):
    """Provenance dataclass serialisation and completeness."""

    def test_to_dict_includes_all_l2_fields(self):
        p = Provenance(
            source_filing="10-K_FY2024.clean.md",
            source_location="income_statement:tbl3",
            table_index=3,
            table_title="Consolidated Statements of Income",
            row_label="Total revenue",
            col_label="Dec 31, 2024",
            row=5,
            col=2,
            raw_text="83,902",
            extraction_method="table",
        )
        d = p.to_dict()
        self.assertEqual(d["source_filing"], "10-K_FY2024.clean.md")
        self.assertEqual(d["table_index"], 3)
        self.assertEqual(d["table_title"], "Consolidated Statements of Income")
        self.assertEqual(d["row_label"], "Total revenue")
        self.assertEqual(d["col_label"], "Dec 31, 2024")
        self.assertEqual(d["row"], 5)
        self.assertEqual(d["col"], 2)
        self.assertEqual(d["raw_text"], "83,902")
        self.assertEqual(d["extraction_method"], "table")

    def test_to_dict_omits_empty_optional(self):
        p = Provenance(source_filing="f.md")
        d = p.to_dict()
        self.assertIn("source_filing", d)
        self.assertNotIn("table_index", d)
        self.assertNotIn("table_title", d)
        self.assertNotIn("extraction_method", d)

    def test_field_result_to_dict_flattens_provenance(self):
        fr = FieldResult(
            value=1000.0,
            provenance=Provenance(
                source_filing="f.md",
                table_index=0,
                table_title="Income",
                row_label="Revenue",
                col_label="FY2024",
                row=1,
                col=0,
                raw_text="1,000",
                extraction_method="table",
            ),
            scale="units",
            confidence="high",
        )
        d = fr.to_dict()
        self.assertEqual(d["value"], 1000.0)
        self.assertEqual(d["source_filing"], "f.md")
        self.assertEqual(d["table_index"], 0)
        self.assertEqual(d["extraction_method"], "table")

    def test_extraction_method_values(self):
        """extraction_method must be one of the known values or empty."""
        allowed = {"table", "narrative", "manual", ""}
        for m in allowed:
            p = Provenance(extraction_method=m)
            self.assertIn(p.extraction_method, allowed)


# ── Integration: check extraction_result.json files ────────────────────────

CASES_DIR = pathlib.Path(__file__).resolve().parents[2] / "cases"


def _iter_field_dicts(result_path: pathlib.Path):
    """Yield (period_key, field_name, field_dict) from an extraction result."""
    with open(result_path) as f:
        data = json.load(f)
    for pk, period_data in data.get("periods", {}).items():
        for fn, fd in period_data.get("fields", {}).items():
            if isinstance(fd, dict) and "value" in fd:
                yield pk, fn, fd


def _l2_complete(fd: dict) -> bool:
    """Return True if a field dict has complete L2 provenance."""
    method = fd.get("extraction_method", "")
    has_sf = bool(fd.get("source_filing"))
    if method == "narrative":
        return has_sf and bool(fd.get("raw_text"))
    if method == "manual":
        return has_sf
    if method == "ixbrl":
        # iXBRL L2: concept name in row_label, period in col_label,
        # displayed value in raw_text — no table coordinates needed.
        return (
            has_sf
            and bool(fd.get("row_label"))
            and bool(fd.get("col_label"))
            and bool(fd.get("raw_text"))
        )
    # Table-sourced fields need full coordinates
    return (
        has_sf
        and fd.get("table_index") is not None
        and bool(fd.get("table_title"))
        and bool(fd.get("row_label"))
        and bool(fd.get("col_label"))
        and fd.get("row") is not None
        and fd.get("col") is not None
        and bool(fd.get("raw_text"))
    )


class TestProvenanceOnExtractionResults(unittest.TestCase):
    """Verify L2 provenance completeness on already-extracted cases.

    These tests only run if extraction_result.json exists for a case.
    They validate that the currently saved results have proper provenance.
    """

    def _check_case(self, ticker: str):
        result_path = CASES_DIR / ticker / "extraction_result.json"
        if not result_path.exists():
            self.skipTest(f"No extraction_result.json for {ticker}")

        total = 0
        incomplete = []
        for pk, fn, fd in _iter_field_dicts(result_path):
            total += 1
            if not _l2_complete(fd):
                incomplete.append(f"  {pk}/{fn}: method={fd.get('extraction_method', '')!r}")

        if total == 0:
            self.skipTest(f"No fields in extraction_result.json for {ticker}")

        pct = 100 * (total - len(incomplete)) / total
        self.assertEqual(
            len(incomplete), 0,
            f"{ticker}: {len(incomplete)}/{total} fields ({100-pct:.1f}%) lack L2 provenance:\n"
            + "\n".join(incomplete[:20]),
        )


def _make_case_test(ticker: str):
    def test_method(self):
        self._check_case(ticker)
    test_method.__name__ = f"test_provenance_l2_{ticker}"
    test_method.__doc__ = f"L2 provenance completeness for {ticker}"
    return test_method


# Dynamically generate one test method per case directory
for _case_dir in sorted(CASES_DIR.iterdir()):
    if _case_dir.is_dir() and (_case_dir / "case.json").exists():
        _ticker = _case_dir.name
        setattr(TestProvenanceOnExtractionResults,
                f"test_provenance_l2_{_ticker}",
                _make_case_test(_ticker))


if __name__ == "__main__":
    unittest.main()
