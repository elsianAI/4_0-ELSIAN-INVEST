"""CLI entry point for ELSIAN 4.0."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from elsian.acquire.registry import get_fetcher
from elsian.evaluate.evaluator import evaluate
from elsian.evaluate.dashboard import format_dashboard
from elsian.models.case import CaseConfig
from elsian.models.result import ExtractionResult, DashboardRow

logger = logging.getLogger(__name__)

CASES_DIR = Path(__file__).resolve().parent.parent / "cases"


def _find_case_dir(ticker: str) -> Path | None:
    """Find case directory for a ticker."""
    d = CASES_DIR / ticker
    if d.exists():
        return d
    for child in CASES_DIR.iterdir():
        if child.is_dir() and child.name.upper() == ticker.upper():
            return child
    return None


def _load_extraction_result(case_dir: Path) -> ExtractionResult | None:
    """Load extraction_result.json from a case directory."""
    result_file = case_dir / "extraction_result.json"
    if not result_file.exists():
        return None
    data = json.loads(result_file.read_text(encoding="utf-8"))
    from elsian.models.field import FieldResult, Provenance
    from elsian.models.result import PeriodResult

    result = ExtractionResult(
        schema_version=data.get("schema_version", "2.0"),
        ticker=data.get("ticker", ""),
        currency=data.get("currency", "USD"),
    )
    for pk, pv in data.get("periods", {}).items():
        pr = PeriodResult(
            fecha_fin=pv.get("fecha_fin", ""),
            tipo_periodo=pv.get("tipo_periodo", ""),
        )
        for fname, fdata in pv.get("fields", {}).items():
            pr.fields[fname] = FieldResult(
                value=fdata.get("value", 0),
                provenance=Provenance(
                    source_filing=fdata.get("source_filing", ""),
                    source_location=fdata.get("source_location", ""),
                ),
                scale=fdata.get("scale", "raw"),
                confidence=fdata.get("confidence", "high"),
            )
        result.periods[pk] = pr
    return result


def cmd_acquire(args: argparse.Namespace) -> None:
    """Download filings for a ticker."""
    case_dir = _find_case_dir(args.ticker)
    if not case_dir:
        print(f"Case not found: {args.ticker}")
        sys.exit(1)

    case = CaseConfig.from_file(case_dir)
    fetcher = get_fetcher(case)

    # For fetchers with acquire(), use it for detailed output
    if hasattr(fetcher, 'acquire'):
        result = fetcher.acquire(case)
        manifest_path = case_dir / "filings_manifest.json"
        manifest_path.write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"{args.ticker}: {result.filings_downloaded} filings downloaded ({result.source})")
        if result.gaps:
            for gap in result.gaps:
                print(f"  GAP: {gap}")
        print(f"  Coverage: {result.filings_coverage_pct}%")
        print(f"  Saved manifest to {manifest_path}")
    else:
        filings = fetcher.fetch(case)
        print(f"{args.ticker}: {len(filings)} filings found")


def cmd_extract(args: argparse.Namespace) -> None:
    """Run extraction on a ticker."""
    from elsian.extract.phase import ExtractPhase

    case_dir = _find_case_dir(args.ticker)
    if not case_dir:
        print(f"Case not found: {args.ticker}")
        sys.exit(1)

    phase = ExtractPhase()
    result = phase.extract(str(case_dir))

    # Save extraction result
    out_path = case_dir / "extraction_result.json"
    out_path.write_text(
        json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    total_fields = sum(len(pr.fields) for pr in result.periods.values())
    print(
        f"{args.ticker}: extracted {total_fields} fields across "
        f"{len(result.periods)} periods from {result.filings_used} filings"
    )
    print(f"  Saved to {out_path}")


def _convert_filings(case_dir: Path, force: bool = False) -> dict:
    """Convert .htm → .clean.md and .pdf → .txt for all filings in case_dir.

    Args:
        case_dir: Path to the case directory.
        force: Re-convert even if the output file already exists.

    Returns:
        Dict with keys: total, converted, skipped, failed.
    """
    from elsian.convert.html_to_markdown import convert as _html_to_md
    from elsian.convert.pdf_to_text import extract_pdf_text

    filings_dir = case_dir / "filings"
    if not filings_dir.exists():
        return {"total": 0, "converted": 0, "skipped": 0, "failed": 0}

    converted = 0
    skipped = 0
    failed = 0
    total = 0

    for filing_path in sorted(filings_dir.iterdir()):
        if not filing_path.is_file():
            continue

        suffix = filing_path.suffix.lower()

        if suffix == ".htm":
            total += 1
            out_path = filings_dir / f"{filing_path.stem}.clean.md"
            if out_path.exists() and not force:
                skipped += 1
                continue
            try:
                clean_md = _html_to_md(filing_path)
                if clean_md:
                    out_path.write_text(clean_md, encoding="utf-8")
                    converted += 1
                else:
                    # Empty output — not useful, but not a failure
                    skipped += 1
            except Exception as exc:
                logger.warning("Convert failed %s: %s", filing_path.name, exc)
                failed += 1

        elif suffix == ".pdf":
            total += 1
            out_path = filings_dir / f"{filing_path.stem}.txt"
            if out_path.exists() and not force:
                skipped += 1
                continue
            try:
                content = filing_path.read_bytes()
                text = extract_pdf_text(content)
                out_path.write_text(text, encoding="utf-8")
                converted += 1
            except Exception as exc:
                logger.warning("Convert failed %s: %s", filing_path.name, exc)
                failed += 1

    return {
        "total": total,
        "converted": converted,
        "skipped": skipped,
        "failed": failed,
    }


def _run_pipeline_for_ticker(
    ticker: str,
    args: argparse.Namespace,
) -> tuple[bool, str]:
    """Run the full processing pipeline for one ticker.

    Phases: [acquire →] convert → extract → evaluate → [assemble]

    Returns:
        (success, one_line_summary)
    """
    from elsian.extract.phase import ExtractPhase
    from elsian.evaluate.evaluator import evaluate as _evaluate

    case_dir = _find_case_dir(ticker)
    if not case_dir:
        print(f"[{ticker}] Case not found")
        return False, "case not found"

    case = CaseConfig.from_file(case_dir)

    # ── Acquire (optional) ────────────────────────────────────────────
    if getattr(args, "with_acquire", False):
        print(f"[Acquire] {ticker} — running acquire...")
        fetcher = get_fetcher(case)
        try:
            if hasattr(fetcher, "acquire"):
                result = fetcher.acquire(case)
                manifest_path = case_dir / "filings_manifest.json"
                manifest_path.write_text(
                    json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                print(
                    f"[Acquire] {ticker} — {result.filings_downloaded} filings downloaded"
                )
            else:
                filings = fetcher.fetch(case)
                print(f"[Acquire] {ticker} — {len(filings)} filings found")
        except Exception as exc:
            print(f"[Acquire] {ticker} — ERROR: {exc}")
            return False, f"acquire failed: {exc}"

    # ── Convert ───────────────────────────────────────────────────────
    force_convert = getattr(args, "force", False)
    filings_dir = case_dir / "filings"
    htm_count = len(list(filings_dir.glob("*.htm"))) if filings_dir.exists() else 0
    pdf_count = len(list(filings_dir.glob("*.pdf"))) if filings_dir.exists() else 0
    conv_total = htm_count + pdf_count

    if conv_total > 0:
        print(f"[Convert] {ticker} — converting {conv_total} filings...")
        conv_stats = _convert_filings(case_dir, force=force_convert)
        print(
            f"[Convert] {ticker} — "
            f"{conv_stats['converted']} new, "
            f"{conv_stats['skipped']} cached, "
            f"{conv_stats['failed']} failed"
        )
    else:
        print(f"[Convert] {ticker} — no .htm/.pdf filings found, skipping")
        conv_stats = {"converted": 0, "skipped": 0, "failed": 0}

    # ── Extract ───────────────────────────────────────────────────────
    print(f"[Extract] {ticker} — extracting fields...")
    phase = ExtractPhase()
    result = phase.extract(str(case_dir))

    out_path = case_dir / "extraction_result.json"
    out_path.write_text(
        json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    total_fields = sum(len(pr.fields) for pr in result.periods.values())
    print(
        f"[Extract] {ticker} — {total_fields} fields across "
        f"{len(result.periods)} periods from {result.filings_used} filings"
    )

    # ── Evaluate ──────────────────────────────────────────────────────
    eval_score: float | None = None
    eval_matched = 0
    eval_total = 0
    expected_path = case_dir / "expected.json"
    eval_ok = True

    if expected_path.exists():
        print(f"[Evaluate] {ticker} — evaluating vs expected.json...")
        report = _evaluate(result, str(expected_path))
        eval_score = report.score
        eval_matched = report.matched
        eval_total = report.total_expected
        eval_ok = report.score == 100.0
        status = "PASS" if eval_ok else "FAIL"
        print(
            f"[Evaluate] {ticker} — {status} {report.score}% "
            f"({report.matched}/{report.total_expected}) "
            f"wrong={report.wrong} missed={report.missed} extra={report.extra}"
        )
        if not eval_ok:
            for d in report.details:
                if d.status != "matched":
                    print(
                        f"           {d.status} {d.period}/{d.field_name} "
                        f"exp={d.expected} got={d.actual}"
                    )
    else:
        print(f"[Evaluate] {ticker} — no expected.json, skipping")

    # ── Assemble ──────────────────────────────────────────────────────
    truth_pack_path: Path | None = None
    if not getattr(args, "skip_assemble", False):
        print(f"[Assemble] {ticker} — building truth_pack.json...")
        try:
            from elsian.assemble.truth_pack import TruthPackAssembler
            assembler = TruthPackAssembler()
            tp = assembler.assemble(case_dir)
            truth_pack_path = case_dir / "truth_pack.json"
            meta = tp.get("metadata", {})
            dm = tp.get("derived_metrics", {})
            derived_count = sum(
                len(v) if isinstance(v, dict) else 1
                for v in dm.values()
                if v is not None and v != {}
            )
            print(
                f"[Assemble] {ticker} — {truth_pack_path.name} "
                f"({meta.get('total_periods', 0)} periods, "
                f"{meta.get('total_fields', 0)} fields, "
                f"{derived_count} derived)"
            )
        except Exception as exc:
            print(f"[Assemble] {ticker} — WARNING: {exc}")
            # Assemble failure is non-fatal — report but don't fail
    else:
        print(f"[Assemble] {ticker} — skipped (--skip-assemble)")

    # ── Final report ──────────────────────────────────────────────────
    conv_new = conv_stats["converted"]
    conv_cached = conv_stats["skipped"]
    eval_str = (
        f"{eval_score:.1f}% ({eval_matched}/{eval_total})"
        if eval_score is not None
        else "N/A"
    )
    assemble_str = str(truth_pack_path) if truth_pack_path else "skipped"

    print(f"\n=== {ticker} Pipeline Complete ===")
    print(f"  Convert:  {conv_total} filings ({conv_new} new, {conv_cached} cached)")
    print(f"  Extract:  {total_fields} fields extracted")
    print(f"  Evaluate: {eval_str}")
    print(f"  Assemble: {assemble_str}")

    one_line = f"{eval_str}"
    return eval_ok, one_line


def cmd_run(args: argparse.Namespace) -> None:
    """Run full pipeline: [acquire →] convert → extract → evaluate → [assemble]."""
    if getattr(args, "all", False):
        # Run all tickers that have both case.json and expected.json
        tickers = sorted(
            d.name for d in CASES_DIR.iterdir()
            if d.is_dir()
            and (d / "case.json").exists()
            and (d / "expected.json").exists()
        )
        if not tickers:
            print("No tickers found with case.json + expected.json")
            sys.exit(1)

        print(f"Running pipeline for {len(tickers)} tickers: {', '.join(tickers)}\n")
        all_ok = True
        results: list[tuple[str, bool, str]] = []
        for ticker in tickers:
            print(f"{'─' * 60}")
            ok, summary = _run_pipeline_for_ticker(ticker, args)
            results.append((ticker, ok, summary))
            if not ok:
                all_ok = False
            print()

        print(f"{'═' * 60}")
        print("=== Pipeline Summary ===")
        for ticker, ok, summary in results:
            status = "PASS" if ok else "FAIL"
            print(f"  {ticker}: {status} — {summary}")

        if not all_ok:
            sys.exit(1)
    else:
        if not args.ticker:
            print("Provide a TICKER or --all")
            sys.exit(1)
        ok, _ = _run_pipeline_for_ticker(args.ticker, args)
        if not ok:
            sys.exit(1)


def cmd_eval(args: argparse.Namespace) -> None:
    """Evaluate extraction vs expected.json."""
    if args.all:
        tickers = sorted(
            d.name for d in CASES_DIR.iterdir()
            if d.is_dir() and (d / "expected.json").exists()
        )
    else:
        tickers = [args.ticker]

    all_ok = True
    for ticker in tickers:
        case_dir = _find_case_dir(ticker)
        if not case_dir:
            print(f"Case not found: {ticker}")
            all_ok = False
            continue

        # Run extraction on-the-fly
        from elsian.extract.phase import ExtractPhase
        phase = ExtractPhase()
        result = phase.extract(str(case_dir))

        report = evaluate(result, str(case_dir / "expected.json"))
        status = "PASS" if report.score == 100.0 else "FAIL"
        print(
            f"{ticker}: {status} -- {report.score}% ({report.matched}/{report.total_expected}) "
            f"wrong={report.wrong} missed={report.missed} extra={report.extra}"
        )

        if report.score < 100.0:
            all_ok = False
            for d in report.details:
                if d.status != "matched":
                    print(f"  {d.status} {d.period}/{d.field_name} exp={d.expected} got={d.actual}")

    if not all_ok:
        sys.exit(1)


def cmd_curate(args: argparse.Namespace) -> None:
    """Generate expected_draft.json from iXBRL or deterministic PDF/text extraction."""
    from elsian.curate_draft import (
        build_expected_draft_from_extraction,
        compare_draft_vs_expected,
    )
    from elsian.extract.ixbrl import (
        parse_ixbrl_filing,
        deduplicate_facts,
        generate_expected_draft,
        run_sanity_checks,
    )

    case_dir = _find_case_dir(args.ticker)
    if not case_dir:
        print(f"Case not found: {args.ticker}")
        sys.exit(1)

    case = CaseConfig.from_file(case_dir)
    filings_dir = case_dir / "filings"

    # Find .htm files
    htm_files = sorted(filings_dir.glob("*.htm")) if filings_dir.exists() else []
    if not htm_files:
        from elsian.extract.phase import ExtractPhase

        print(
            f"{args.ticker}: No iXBRL (.htm) files found. "
            "Falling back to deterministic PDF/text curate."
        )

        conv_stats = _convert_filings(case_dir, force=False)
        print(
            f"  Convert: {conv_stats['converted']} new, "
            f"{conv_stats['skipped']} cached, {conv_stats['failed']} failed"
        )

        phase = ExtractPhase()
        result = phase.extract(str(case_dir))
        extraction_out_path = case_dir / "extraction_result.json"
        extraction_out_path.write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        expected_path = case_dir / "expected.json"
        expected = None
        if expected_path.exists():
            expected = json.loads(expected_path.read_text(encoding="utf-8"))

        draft = build_expected_draft_from_extraction(
            result,
            ticker=case.ticker or args.ticker,
            currency=result.currency or case.currency,
            expected=expected,
        )

        out_path = case_dir / "expected_draft.json"
        out_path.write_text(
            json.dumps(draft, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        periods = draft.get("periods", {})
        validation = draft.get("_validation")
        if validation:
            print(
                f"  Periods: {len(periods)} "
                f"(validation={validation['status']}, "
                f"confidence={validation['confidence_score']:.1f})"
            )
        else:
            print(f"  Periods: {len(periods)}")
        for plabel in sorted(periods.keys()):
            pdata = periods[plabel]
            fields = pdata.get("fields", {})
            gap_info = pdata.get("_gaps", {})
            conf_info = pdata.get("_confidence", {})
            print(
                f"    {plabel}: {len(fields)} fields, "
                f"not_auto_populated={len(gap_info.get('missing_canonicals', []))}, "
                f"confidence={conf_info}"
            )
        if periods:
            print(
                "  Gap note: missing_canonicals = global canonical fields not "
                "auto-populated by the deterministic draft for that period; "
                "it is not proof that the filing must contain them."
            )

        if expected is not None:
            comparison = compare_draft_vs_expected(draft, expected)
            print(
                f"  vs expected.json ({len(comparison['common_periods'])} common periods): "
                f"coverage={comparison['coverage_fields']}/{comparison['total_expected_fields']} "
                f"({comparison['coverage_pct']:.0f}%), "
                f"value_match={comparison['matched_fields']}/{comparison['total_expected_fields']} "
                f"({comparison['value_match_pct']:.0f}%)"
            )
            if comparison["missing_periods"]:
                print(f"  Missing periods vs expected: {', '.join(comparison['missing_periods'])}")
            if comparison["extra_periods"]:
                print(f"  Extra periods vs expected: {', '.join(comparison['extra_periods'])}")

        warnings = draft.get("_validation", {}).get("warnings", [])
        if warnings:
            print(f"  Validation warnings: {len(warnings)}")
            for warning in warnings:
                print(f"    ⚠ {warning}")
        elif validation:
            print("  Validation warnings: none")

        print(f"  Saved to {out_path}")
        return

    # Parse all .htm files
    all_facts = []
    for htm in htm_files:
        facts = parse_ixbrl_filing(
            htm,
            fiscal_year_end_month=case.fiscal_year_end_month,
        )
        all_facts.extend(facts)

    print(f"{args.ticker}: Parsed {len(all_facts)} iXBRL facts from {len(htm_files)} files")
    mapped_count = sum(1 for f in all_facts if f.field is not None)
    print(f"  Mapped to canonical fields: {mapped_count}")

    # Deduplicate: prefer annual filing values
    deduped = deduplicate_facts(all_facts)

    # Generate draft
    draft = generate_expected_draft(
        deduped,
        ticker=case.ticker or args.ticker,
        currency=case.currency,
    )

    # Run sanity checks
    warnings = run_sanity_checks(draft)

    # Save
    out_path = case_dir / "expected_draft.json"
    out_path.write_text(
        json.dumps(draft, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Print summary
    periods = draft.get("periods", {})
    print(f"  Periods: {len(periods)}")
    for plabel in sorted(periods.keys()):
        n_fields = len(periods[plabel].get("fields", {}))
        field_names = sorted(periods[plabel].get("fields", {}).keys())
        print(f"    {plabel}: {n_fields} fields — {', '.join(field_names)}")

    if warnings:
        print(f"  Sanity checks: {len(warnings)} warning(s)")
        for w in warnings:
            print(f"    ⚠ {w}")
    else:
        print("  Sanity checks: all passed")

    # Compare with existing expected.json if available
    expected_path = case_dir / "expected.json"
    if expected_path.exists():
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        comparison = compare_draft_vs_expected(draft, expected)
        print(
            f"  vs expected.json ({len(comparison['common_periods'])} common periods): "
            f"coverage={comparison['coverage_fields']}/{comparison['total_expected_fields']} "
            f"({comparison['coverage_pct']:.0f}%), "
            f"value_match={comparison['matched_fields']}/{comparison['total_expected_fields']} "
            f"({comparison['value_match_pct']:.0f}%)"
        )
        if comparison["missing_periods"]:
            print(f"  Missing periods vs expected: {', '.join(comparison['missing_periods'])}")
        if comparison["extra_periods"]:
            print(f"  Extra periods vs expected: {', '.join(comparison['extra_periods'])}")

    print(f"  Saved to {out_path}")


def cmd_market(args: argparse.Namespace) -> None:
    """Fetch market data snapshot for a ticker."""
    from elsian.acquire.market_data import MarketDataFetcher

    case_dir = _find_case_dir(args.ticker)
    if not case_dir:
        print(f"Case not found: {args.ticker}")
        sys.exit(1)

    case = CaseConfig.from_file(case_dir)
    exchange = getattr(args, "exchange", None)
    country = getattr(args, "country", None)

    # Read exchange/country from case.json if not provided via CLI
    if not exchange:
        case_data = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
        exchange = case_data.get("exchange")
    if not country:
        case_data = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
        country = case_data.get("country")

    fetcher = MarketDataFetcher()
    md = fetcher.fetch_and_save(
        ticker=case.ticker or args.ticker,
        case_dir=case_dir,
        exchange=exchange,
        country=country,
    )

    print(f"{md.ticker}: {md.currency} {md.price}")
    if md.market_cap is not None:
        print(f"  Market cap: {md.currency} {md.market_cap}M")
    if md.shares_outstanding is not None:
        print(f"  Shares outstanding: {md.shares_outstanding}M")
    if md.sector:
        print(f"  Sector: {md.sector}")
    if md.industry:
        print(f"  Industry: {md.industry}")
    if md.high_52w is not None and md.low_52w is not None:
        print(f"  52w range: {md.low_52w} - {md.high_52w}")
    if md.avg_volume_30d is not None:
        print(f"  Avg volume (30d): {md.avg_volume_30d}")
    print(f"  Source: {md.source}")
    print(f"  Saved to {case_dir / '_market_data.json'}")


def cmd_transcripts(args: argparse.Namespace) -> None:
    """Find earnings transcripts and IR presentations."""
    from elsian.acquire.transcripts import TranscriptFinder

    case_dir = _find_case_dir(args.ticker)
    if not case_dir:
        print(f"Case not found: {args.ticker}")
        sys.exit(1)

    case = CaseConfig.from_file(case_dir)
    finder = TranscriptFinder()
    result = finder.find(case)

    # Save result
    out_path = case_dir / "_transcripts.json"
    out_path.write_text(
        json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    transcript_count = sum(1 for s in result.sources if s.tipo == "EARNINGS_TRANSCRIPT")
    presentation_count = sum(
        1 for s in result.sources if s.tipo in ("INVESTOR_PRESENTATION", "ANNUAL_REPORT")
    )
    print(
        f"{args.ticker}: {len(result.sources)} sources found "
        f"({transcript_count} transcripts, {presentation_count} presentations)"
    )
    if result.discarded:
        print(f"  Discarded: {len(result.discarded)}")
    if result.missing:
        for gap in result.missing:
            print(f"  GAP: {gap}")
    print(f"  Saved to {out_path}")


def cmd_compile(args: argparse.Namespace) -> None:
    """Compile multi-fetcher outputs into SourcesPack_v1 for a ticker."""
    from elsian.acquire.sources_compiler import save_sources_pack

    case_dir = _find_case_dir(args.ticker)
    if not case_dir:
        print(f"Case not found: {args.ticker}")
        sys.exit(1)

    out_path = save_sources_pack(args.ticker, case_dir)
    pack = json.loads(out_path.read_text(encoding="utf-8"))
    meta = pack.get("_meta", {}).get("fuentes_consolidadas", {})
    print(
        f"{args.ticker}: {meta.get('total_final', 0)} sources compiled "
        f"({meta.get('duplicados_eliminados', 0)} duplicates removed)"
    )
    by_cat = pack.get("_meta", {}).get("by_category", {})
    for cat, count in sorted(by_cat.items()):
        print(f"  {cat}: {count}")
    print(f"  Saved to {out_path}")


def cmd_coverage(args: argparse.Namespace) -> None:
    """Audit filing coverage for one or all tickers."""
    from elsian.evaluate.coverage_audit import evaluate_case, build_report, render_markdown

    if getattr(args, "all", False):
        report = build_report(CASES_DIR)
        print(render_markdown(report))
        s = report["summary"]
        print(f"Summary: {s['pass_count']}/{s['total_tickers']} PASS, {s['needs_action_count']} NEEDS_ACTION")
        if report["needs_action"]:
            sys.exit(1)
    else:
        if not args.ticker:
            print("Provide a TICKER or --all")
            sys.exit(1)
        case_dir = _find_case_dir(args.ticker)
        if not case_dir:
            print(f"Case not found: {args.ticker}")
            sys.exit(1)
        result = evaluate_case(case_dir)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result["status"] != "PASS":
            sys.exit(1)


def cmd_assemble(args: argparse.Namespace) -> None:
    """Assemble TruthPack_v1 for a ticker."""
    from elsian.assemble.truth_pack import TruthPackAssembler

    case_dir = _find_case_dir(args.ticker)
    if not case_dir:
        print(f"Case not found: {args.ticker}")
        sys.exit(1)

    assembler = TruthPackAssembler()
    tp = assembler.assemble(case_dir)

    # Print summary
    meta = tp.get("metadata", {})
    quality = tp.get("quality", {})
    dm = tp.get("derived_metrics", {})

    print(f"{args.ticker}: TruthPack_v1 assembled")
    print(f"  Periods: {meta.get('total_periods', 0)}")
    print(f"  Fields: {meta.get('total_fields', 0)}")
    print(f"  Quality: {quality.get('validation_status', 'UNKNOWN')} (confidence={quality.get('confidence_score', 0)})")
    if quality.get("warnings"):
        for w in quality["warnings"]:
            print(f"    WARNING: {w}")
    has_market = tp.get("market_data") is not None
    print(f"  Market data: {'YES' if has_market else 'NO'}")
    print(f"  Derived periodo_base: {dm.get('periodo_base', 'N/A')}")
    print(f"  Saved to {case_dir / 'truth_pack.json'}")


def cmd_source_map(args: argparse.Namespace) -> None:
    """Build a SourceMap_v1 artifact for a ticker."""
    from elsian.assemble.source_map import SourceMapBuilder

    case_dir = _find_case_dir(args.ticker)
    if not case_dir:
        print(f"Case not found: {args.ticker}")
        sys.exit(1)

    extraction_result_path = case_dir / "extraction_result.json"
    if not extraction_result_path.exists():
        print(
            (
                f"{args.ticker}: extraction_result.json no existe en {case_dir}. "
                "Ejecuta `elsian extract TICKER` o `elsian run TICKER` antes de `source-map`."
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    output_path = Path(args.output) if getattr(args, "output", None) else None
    builder = SourceMapBuilder()
    sm = builder.build(case_dir, output_path=output_path)

    out_path = output_path if output_path else case_dir / "source_map.json"
    summary = sm.get("summary", {})
    resolved = summary.get("resolved_fields", 0)
    total = summary.get("total_fields", 0)
    if total and resolved == total:
        status = "FULL"
        exit_code = 0
    elif resolved > 0:
        status = "PARTIAL"
        exit_code = 0
    else:
        status = "EMPTY"
        exit_code = 1

    stream = sys.stderr if exit_code else sys.stdout
    print(f"{args.ticker}: SourceMap_v1 {status}", file=stream)
    print(
        f"  Resolved: {resolved}/{total} ({summary.get('resolution_pct', 0)}%)",
        file=stream,
    )
    by_kind = summary.get("by_pointer_kind", {})
    if by_kind:
        for kind, count in sorted(by_kind.items()):
            print(f"  {kind}: {count}", file=stream)
    sample_target = None
    periods = sm.get("periods", {})
    for period_data in periods.values():
        for field_data in period_data.get("fields", {}).values():
            if field_data.get("resolution_status") == "resolved":
                sample_target = field_data.get("click_target")
                break
        if sample_target:
            break
    if sample_target:
        print(f"  Sample click target: {sample_target}", file=stream)
    if status == "PARTIAL":
        print("  Status: partial resolution; review unresolved fields before relying on the artifact.", file=stream)
    elif status == "EMPTY":
        print("  Status: no fields resolved; artifact written only for diagnosis.", file=stream)
    print(f"  Saved to {out_path}", file=stream)
    if exit_code:
        sys.exit(exit_code)


def cmd_dashboard(args: argparse.Namespace) -> None:
    """Show dashboard summary."""
    rows: list[DashboardRow] = []
    for d in sorted(CASES_DIR.iterdir()):
        if not d.is_dir() or not (d / "expected.json").exists():
            continue
        case = CaseConfig.from_file(d)
        result = _load_extraction_result(d)
        if not result:
            continue
        report = evaluate(result, str(d / "expected.json"))
        rows.append(DashboardRow(
            ticker=case.ticker or d.name,
            source=case.source_hint,
            filings=result.filings_used,
            periods=len(result.periods),
            expected=report.total_expected,
            matched=report.matched,
            score=report.score,
        ))

    print(format_dashboard(rows))


def cmd_discover(args: argparse.Namespace) -> None:
    """Auto-discover ticker metadata and generate case.json."""
    from elsian.discover.discover import TickerDiscoverer, parse_ticker_suffix

    discoverer = TickerDiscoverer()
    result = discoverer.discover(args.ticker)

    # Determine case directory name (strip suffix for non-US tickers)
    base_ticker, _suffix = parse_ticker_suffix(args.ticker)
    case_dir = CASES_DIR / base_ticker.upper()
    case_file = case_dir / "case.json"

    # Check existing
    if case_file.exists() and not args.force:
        print(f"ERROR: {case_file} already exists. Use --force to overwrite.")
        sys.exit(1)

    # Create directory and write case.json
    case_dir.mkdir(parents=True, exist_ok=True)
    case_dict = result.to_case_dict()
    case_file.write_text(
        json.dumps(case_dict, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Print summary
    print(f"Discovered: {args.ticker}")
    print(f"  Company:    {result.company_name or '(unknown)'}")
    print(f"  Exchange:   {result.exchange or '(unknown)'}")
    print(f"  Country:    {result.country or '(unknown)'}")
    print(f"  Currency:   {result.currency or '(unknown)'}")
    print(f"  Source:     {result.source_hint or '(unknown)'}")
    print(f"  Accounting: {result.accounting_standard or '(unknown)'}")
    print(f"  CIK:        {result.cik or '(N/A)'}")
    print(f"  FY end:     month {result.fiscal_year_end_month or '(unknown)'}")
    print(f"  Sector:     {result.sector or '(unknown)'}")
    if result.web_ir:
        print(f"  Web IR:     {result.web_ir}")
    if result.warnings:
        print("  Warnings:")
        for w in result.warnings:
            print(f"    - {w}")
    print(f"  Saved to {case_file}")


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(prog="elsian", description="ELSIAN 4.0 CLI")
    sub = parser.add_subparsers(dest="command")

    p_acquire = sub.add_parser("acquire", help="Download filings for a ticker")
    p_acquire.add_argument("ticker")
    p_acquire.set_defaults(func=cmd_acquire)

    p_extract = sub.add_parser("extract", help="Extract fields from filings")
    p_extract.add_argument("ticker")
    p_extract.set_defaults(func=cmd_extract)

    p_run = sub.add_parser(
        "run",
        help="Full pipeline: [acquire →] convert → extract → evaluate → [assemble]",
    )
    p_run.add_argument("ticker", nargs="?", default="", help="Ticker symbol, or omit with --all")
    p_run.add_argument("--all", action="store_true", help="Run all tickers with case.json + expected.json")
    p_run.add_argument("--with-acquire", dest="with_acquire", action="store_true", help="Run acquire before convert")
    p_run.add_argument("--skip-assemble", dest="skip_assemble", action="store_true", help="Skip truth_pack generation")
    p_run.add_argument("--force", action="store_true", help="Re-convert filings even if .clean.md already exists")
    p_run.set_defaults(func=cmd_run)

    p_eval = sub.add_parser("eval", help="Evaluate extraction vs expected.json")
    p_eval.add_argument("ticker", nargs="?", default="")
    p_eval.add_argument("--all", action="store_true")
    p_eval.set_defaults(func=cmd_eval)

    p_curate = sub.add_parser(
        "curate",
        help="Generate expected_draft.json from iXBRL or deterministic extraction",
    )
    p_curate.add_argument("ticker")
    p_curate.set_defaults(func=cmd_curate)

    p_market = sub.add_parser("market", help="Fetch market data snapshot")
    p_market.add_argument("ticker")
    p_market.add_argument("--exchange", default=None, help="Exchange code (e.g. NASDAQ, EPA)")
    p_market.add_argument("--country", default=None, help="Country code (e.g. US, FR)")
    p_market.set_defaults(func=cmd_market)

    p_transcripts = sub.add_parser("transcripts", help="Find earnings transcripts and IR presentations")
    p_transcripts.add_argument("ticker")
    p_transcripts.set_defaults(func=cmd_transcripts)

    p_compile = sub.add_parser("compile", help="Compile sources into SourcesPack_v1")
    p_compile.add_argument("ticker")
    p_compile.set_defaults(func=cmd_compile)

    p_coverage = sub.add_parser("coverage", help="Audit filing coverage for a ticker or all")
    p_coverage.add_argument("ticker", nargs="?", default="")
    p_coverage.add_argument("--all", action="store_true")
    p_coverage.set_defaults(func=cmd_coverage)

    p_dash = sub.add_parser("dashboard", help="Summary table of all cases")
    p_dash.set_defaults(func=cmd_dashboard)

    p_assemble = sub.add_parser("assemble", help="Assemble TruthPack_v1 for a ticker")
    p_assemble.add_argument("ticker")
    p_assemble.set_defaults(func=cmd_assemble)

    p_source_map = sub.add_parser(
        "source-map",
        help="Build SourceMap_v1 provenance artifact for a ticker",
    )
    p_source_map.add_argument("ticker")
    p_source_map.add_argument(
        "--output",
        default=None,
        help="Write source_map.json to this path instead of cases/<TICKER>/source_map.json",
    )
    p_source_map.set_defaults(func=cmd_source_map)

    p_discover = sub.add_parser("discover", help="Auto-discover ticker metadata → case.json")
    p_discover.add_argument("ticker", help="Ticker symbol (e.g. AAPL, TEP.PA, KAR.AX)")
    p_discover.add_argument("--force", action="store_true", help="Overwrite existing case.json")
    p_discover.set_defaults(func=cmd_discover)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
