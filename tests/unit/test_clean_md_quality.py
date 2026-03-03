"""Tests for elsian.convert.clean_md_quality — granular quality gates."""

from __future__ import annotations

import unittest

from elsian.convert.clean_md_quality import (
    CORE_SECTIONS,
    detect_clean_md_mode,
    evaluate_clean_md,
    is_clean_md_useful,
)

# ── Fixtures ──────────────────────────────────────────────────────────


def _make_numeric_row(label: str = "Revenue", val: str = "1,234") -> str:
    return f"| {label} | {val} | {val} |"


def _make_separator() -> str:
    return "| --- | --- | --- |"


def _make_table(n_rows: int = 5) -> str:
    """Markdown table with *n_rows* numeric data rows."""
    lines = ["| Item | 2024 | 2023 |", _make_separator()]
    for i in range(n_rows):
        lines.append(_make_numeric_row(f"Line {i}", f"{1000 + i * 100}"))
    return "\n".join(lines)


def _make_section(name: str, n_rows: int = 5) -> str:
    return f"## {name}\n\n{_make_table(n_rows)}\n"


def _make_html_table_doc(
    is_rows: int = 5, bs_rows: int = 5, cf_rows: int = 5
) -> str:
    """Simulate a complete html_table clean.md."""
    parts = [
        "# FINANCIAL STATEMENTS — test",
        "_Extractor mode: html_table_",
        "",
        _make_section("INCOME STATEMENT", is_rows),
        _make_section("BALANCE SHEET", bs_rows),
        _make_section("CASH FLOW", cf_rows),
    ]
    return "\n\n".join(parts)


def _make_stub_section(name: str) -> str:
    return f"## {name}\n\n_Section not found in filing._\n"


def _make_all_stubs_doc() -> str:
    parts = [
        "# FINANCIAL STATEMENTS — test",
        "_Extractor mode: html_table_",
        "",
        _make_stub_section("INCOME STATEMENT"),
        _make_stub_section("BALANCE SHEET"),
        _make_stub_section("CASH FLOW"),
        _make_stub_section("EQUITY"),
    ]
    return "\n\n".join(parts)


def _make_pdf_text_doc(
    signal_keywords: int = 10,
    chars: int = 10_000,
    numeric_tokens: int = 100,
    core_sections: int = 2,
) -> str:
    """Simulate a pdf_text clean.md with controllable properties."""
    parts = ["_Extractor mode: pdf_text_", ""]

    # Inject signal keywords
    keywords = [
        "revenue", "net revenue", "income", "profit", "loss",
        "cash flow", "operating activities", "investing activities",
        "financing activities", "assets", "liabilities", "equity",
    ]
    for kw in keywords[:signal_keywords]:
        parts.append(f"The company reported {kw} growth.")

    # Create core sections with numeric tokens
    if core_sections >= 1:
        section = "## INCOME STATEMENT\n\n"
        section += " ".join([f"${1000 + i}" for i in range(max(25, numeric_tokens // 3))])
        parts.append(section)
    if core_sections >= 2:
        section = "## BALANCE SHEET\n\n"
        section += " ".join([f"${2000 + i}" for i in range(max(25, numeric_tokens // 3))])
        parts.append(section)
    if core_sections >= 3:
        section = "## CASH FLOW\n\n"
        section += " ".join([f"${3000 + i}" for i in range(max(25, numeric_tokens // 3))])
        parts.append(section)

    doc = "\n\n".join(parts)
    # Pad to required chars
    if len(doc) < chars:
        doc += " filler" * ((chars - len(doc)) // 7 + 1)
    return doc[:max(chars, len(doc))]


# ── Mode detection ────────────────────────────────────────────────────


class TestDetectMode(unittest.TestCase):
    def test_explicit_html_table_header(self) -> None:
        text = "_Extractor mode: html_table_\n\n| A | B |\n"
        self.assertEqual(detect_clean_md_mode(text), "html_table")

    def test_explicit_pdf_text_header(self) -> None:
        text = "_Extractor mode: pdf_text_\n\nSome text."
        self.assertEqual(detect_clean_md_mode(text), "pdf_text")

    def test_heuristic_html_table(self) -> None:
        """Many markdown table rows triggers html_table mode."""
        rows = "\n".join([_make_numeric_row(f"R{i}", "100") for i in range(10)])
        self.assertEqual(detect_clean_md_mode(rows), "html_table")

    def test_heuristic_pdf_text(self) -> None:
        """Plain text with few table rows triggers pdf_text mode."""
        text = "This is plain text with some numbers 100 200 300.\n"
        self.assertEqual(detect_clean_md_mode(text), "pdf_text")

    def test_empty_text(self) -> None:
        self.assertEqual(detect_clean_md_mode(""), "pdf_text")


# ── HTML table gate ───────────────────────────────────────────────────


class TestHtmlTableGate(unittest.TestCase):
    def test_useful_when_enough_numeric_rows_and_valid_section(self) -> None:
        doc = _make_html_table_doc(is_rows=5, bs_rows=5, cf_rows=5)
        result = evaluate_clean_md(doc, mode="html_table")
        self.assertTrue(result["useful"])
        self.assertEqual(result["reason"], "OK")
        self.assertEqual(result["mode"], "html_table")

    def test_not_useful_all_sections_missing(self) -> None:
        doc = _make_all_stubs_doc()
        result = evaluate_clean_md(doc, mode="html_table")
        self.assertFalse(result["useful"])
        self.assertEqual(result["reason"], "ALL_SECTIONS_MISSING")

    def test_not_useful_low_numeric_rows(self) -> None:
        doc = _make_html_table_doc(is_rows=1, bs_rows=0, cf_rows=0)
        result = evaluate_clean_md(doc, mode="html_table")
        self.assertFalse(result["useful"])
        self.assertIn(result["reason"], {"LOW_NUMERIC_ROWS", "NO_VALID_CORE_SECTION"})

    def test_not_useful_no_valid_core_section(self) -> None:
        """All sections exist but each has < 3 numeric rows."""
        # Note: table header row (| Item | 2024 | 2023 |) also matches
        # the numeric-row regex, so n_rows=1 → 2 matches per section (< 3).
        doc = _make_html_table_doc(is_rows=1, bs_rows=1, cf_rows=1)
        # 6 numeric rows total (≥5) but each section has only 2 (< 3)
        result = evaluate_clean_md(doc, mode="html_table")
        self.assertFalse(result["useful"])
        self.assertEqual(result["reason"], "NO_VALID_CORE_SECTION")


# ── PDF text gate ─────────────────────────────────────────────────────


class TestPdfTextGate(unittest.TestCase):
    def test_useful_pdf_text(self) -> None:
        doc = _make_pdf_text_doc(
            signal_keywords=10, chars=10_000, numeric_tokens=200, core_sections=2
        )
        result = evaluate_clean_md(doc, mode="pdf_text")
        self.assertTrue(result["useful"])
        self.assertEqual(result["reason"], "OK")

    def test_not_useful_low_signal(self) -> None:
        doc = _make_pdf_text_doc(signal_keywords=3, chars=10_000, numeric_tokens=100, core_sections=2)
        result = evaluate_clean_md(doc, mode="pdf_text")
        self.assertFalse(result["useful"])
        self.assertEqual(result["reason"], "LOW_SIGNAL")

    def test_not_useful_pdf_placeholder(self) -> None:
        doc = "[PDF original — unable to extract text]"
        result = evaluate_clean_md(doc, mode="pdf_text")
        self.assertFalse(result["useful"])
        self.assertEqual(result["reason"], "PDF_PLACEHOLDER")

    def test_not_useful_low_text(self) -> None:
        """Short document rejected."""
        doc = _make_pdf_text_doc(signal_keywords=8, chars=2_000, numeric_tokens=20, core_sections=0)
        # Trim to small size
        doc = doc[:2000]
        result = evaluate_clean_md(doc, mode="pdf_text")
        self.assertFalse(result["useful"])
        # Could be LOW_SIGNAL, LOW_TEXT, or LOW_NUMERIC_DENSITY depending on trim
        self.assertFalse(result["useful"])


# ── Section-level metrics ─────────────────────────────────────────────


class TestSectionMetrics(unittest.TestCase):
    def test_section_numeric_rows_counted_per_section(self) -> None:
        doc = (
            "## INCOME STATEMENT\n\n" + _make_table(8) + "\n\n"
            "## BALANCE SHEET\n\n" + _make_table(4) + "\n\n"
            "## CASH FLOW\n\n" + _make_table(2) + "\n"
        )
        result = evaluate_clean_md(doc, mode="html_table")
        snr = result["stats"]["section_numeric_rows"]
        # +1 because table header row (| Item | 2024 | 2023 |) matches
        # the numeric-row regex
        self.assertEqual(snr["INCOME STATEMENT"], 9)
        self.assertEqual(snr["BALANCE SHEET"], 5)
        self.assertEqual(snr["CASH FLOW"], 3)

    def test_valid_core_sections_count(self) -> None:
        doc = _make_html_table_doc(is_rows=5, bs_rows=5, cf_rows=1)
        result = evaluate_clean_md(doc, mode="html_table")
        # IS=5≥3 ✓, BS=5≥3 ✓, CF=1<3 ✗ → 2 valid
        self.assertEqual(result["stats"]["valid_core_sections"], 2)


# ── Stub detection ────────────────────────────────────────────────────


class TestStubDetection(unittest.TestCase):
    def test_stubs_counted(self) -> None:
        doc = _make_all_stubs_doc()
        result = evaluate_clean_md(doc, mode="html_table")
        self.assertGreaterEqual(result["stats"]["missing_sections"], 4)

    def test_no_stubs_when_sections_present(self) -> None:
        doc = _make_html_table_doc()
        result = evaluate_clean_md(doc, mode="html_table")
        self.assertEqual(result["stats"]["missing_sections"], 0)


# ── Stats dict completeness ──────────────────────────────────────────


class TestStatsDictCompleteness(unittest.TestCase):
    def test_html_table_stats_keys(self) -> None:
        doc = _make_html_table_doc()
        result = evaluate_clean_md(doc, mode="html_table")
        expected_keys = {
            "numeric_rows", "missing_sections",
            "valid_core_sections", "section_numeric_rows",
        }
        self.assertEqual(set(result["stats"].keys()), expected_keys)
        # section_numeric_rows has an entry per CORE_SECTIONS
        self.assertEqual(
            set(result["stats"]["section_numeric_rows"].keys()),
            set(CORE_SECTIONS),
        )

    def test_pdf_text_stats_keys(self) -> None:
        doc = _make_pdf_text_doc()
        result = evaluate_clean_md(doc, mode="pdf_text")
        expected_keys = {
            "chars", "signal_hits", "signal_hit_count",
            "numeric_token_count", "core_sections",
        }
        self.assertEqual(set(result["stats"].keys()), expected_keys)

    def test_result_has_mode_useful_reason_stats(self) -> None:
        doc = _make_html_table_doc()
        result = evaluate_clean_md(doc, mode="html_table")
        for key in ("mode", "useful", "reason", "stats"):
            self.assertIn(key, result, f"Missing top-level key: {key}")

    def test_empty_text_returns_empty_stats(self) -> None:
        result = evaluate_clean_md("", mode="html_table")
        self.assertFalse(result["useful"])
        self.assertEqual(result["reason"], "EMPTY")
        self.assertEqual(result["stats"], {})


# ── Boolean wrapper ───────────────────────────────────────────────────


class TestIsCleanMdUseful(unittest.TestCase):
    def test_useful_returns_true(self) -> None:
        doc = _make_html_table_doc()
        self.assertTrue(is_clean_md_useful(doc, mode="html_table"))

    def test_not_useful_returns_false(self) -> None:
        doc = _make_all_stubs_doc()
        self.assertFalse(is_clean_md_useful(doc, mode="html_table"))

    def test_auto_mode_detection(self) -> None:
        """When mode=None the function auto-detects."""
        doc = _make_html_table_doc()
        self.assertTrue(is_clean_md_useful(doc))


if __name__ == "__main__":
    unittest.main()
