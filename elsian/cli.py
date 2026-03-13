"""CLI entry point for ELSIAN 4.0."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from elsian.acquire.registry import get_fetcher
from elsian.analyze.discovery_baseline import build_eval_output_payload
from elsian.evaluate.evaluator import evaluate
from elsian.evaluate.dashboard import format_dashboard
from elsian.models.case import CaseConfig
from elsian.models.result import ExtractionResult, DashboardRow
from elsian.run_metrics import write_run_metrics

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
    """Run the full processing pipeline for one ticker via Pipeline.

    Phases: [acquire →] convert → extract → evaluate → [assemble]

    Severity contract (BL-063):
      fatal   → pipeline stops; returns (False, "fatal error in pipeline")
      warning → recorded, pipeline continues (e.g. EvaluatePhase FAIL, Assemble error)
      ok      → normal

    Returns:
        (eval_ok, one_line_summary)  — eval_ok=False when score < 100%.
        Returns (False, "fatal error…") on fatal phase errors.
    """
    from elsian.context import PipelineContext
    from elsian.pipeline import Pipeline
    from elsian.convert.phase import ConvertPhase
    from elsian.extract.phase import ExtractPhase
    from elsian.evaluate.phase import EvaluatePhase
    from elsian.models.result import PhaseResult as _PhaseResult

    case_dir = _find_case_dir(ticker)
    if not case_dir:
        print(f"[{ticker}] Case not found")
        return False, "case not found"

    case = CaseConfig.from_file(case_dir)
    context = PipelineContext(case=case)

    # Canonical ticker from case.json (used for workspace subdir and run_metrics).
    # Always derive from case.ticker so the value is stable regardless of how
    # the user typed the CLI argument (e.g. "tzoo" → "TZOO").
    canonical_ticker = case.ticker if case.ticker else ticker

    # BL-070: workspace path resolution — runtime artifacts land outside cases/
    # Use canonical ticker from case.json so the runtime subdir is always uppercase
    # regardless of the casing the user typed (e.g. "tzoo" → "TZOO").
    workspace = getattr(args, "workspace", None)
    if workspace:
        runtime_dir = Path(workspace) / canonical_ticker
        runtime_dir.mkdir(parents=True, exist_ok=True)
        context.runtime_dir = str(runtime_dir)
    else:
        runtime_dir = case_dir

    with_acquire = getattr(args, "with_acquire", False)
    skip_assemble = getattr(args, "skip_assemble", False)
    force = getattr(args, "force", False)
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()

    # ── Build phase sequence ───────────────────────────────────────────
    phases: list = []
    if with_acquire:
        from elsian.acquire.phase import AcquirePhase
        phases.append(AcquirePhase())

    phases.append(ConvertPhase(force=force))
    phases.append(ExtractPhase())
    phases.append(EvaluatePhase())

    if not skip_assemble:
        from elsian.assemble.phase import AssemblePhase
        phases.append(AssemblePhase())

    # ── Per-phase progress reporter (observability only) ───────────────
    def _on_done(result: _PhaseResult) -> None:
        label = result.phase_name.replace("Phase", "")
        sev = f" [{result.severity.upper()}]" if result.severity != "ok" else ""
        print(f"[{label}]{sev} {ticker} — {result.message}")
        # Print FAIL detail lines from EvaluatePhase
        if result.phase_name == "EvaluatePhase" and result.data:
            report = result.data
            for d in report.details:
                if d.status != "matched":
                    print(
                        f"           {d.status} {d.period}/{d.field_name} "
                        f"exp={d.expected} got={d.actual}"
                    )

    # ── Run ───────────────────────────────────────────────────────────
    Pipeline(phases, on_phase_done=_on_done).run(context)
    finished_at = datetime.now(timezone.utc).isoformat()

    # ── Interpret results ─────────────────────────────────────────────
    fatal = any(r.is_fatal for r in context.phase_results)
    eval_result = next(
        (r for r in context.phase_results if r.phase_name == "EvaluatePhase"), None
    )
    # eval_ok_json: True=passed, False=failed, None=skipped or fatal (not applicable)
    if fatal:
        eval_ok_json: bool | None = None
        eval_str = "FATAL"
    elif eval_result is not None and eval_result.data is not None:
        report = eval_result.data
        eval_ok_json = report.score == 100.0
        eval_str = f"{report.score:.1f}% ({report.matched}/{report.total_expected})"
    elif eval_result is not None and not eval_result.diagnostics:
        # EvaluatePhase ran but skipped (no expected.json): no data, no diagnostics
        eval_ok_json = None
        eval_str = "skipped"
    else:
        eval_ok_json = None
        eval_str = "N/A"
    # Exit code: None (skipped) counts as success; only False (quality FAIL) causes failure
    exit_ok = (not fatal) and (eval_ok_json is not False)

    # ── Write run_metrics.json (best-effort, always — even on fatal) ───
    # BL-070: write to runtime_dir (workspace when provided, else case_dir)
    # Use canonical_ticker so run_metrics["ticker"] always matches case.json,
    # not the raw CLI argument (e.g. "tzoo" vs "TZOO").
    _metrics_path: Path | None = None
    try:
        _metrics_path = write_run_metrics(
            runtime_dir,
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            ticker=canonical_ticker,
            source_hint=case.source_hint,
            with_acquire=with_acquire,
            skip_assemble=skip_assemble,
            force=force,
            context=context,
            eval_ok=eval_ok_json,
        )
    except Exception as exc:
        logger.warning("Failed to write run_metrics.json: %s", exc)

    if fatal:
        return False, "fatal error in pipeline"

    # ── Save extraction result (only when no fatal phase) ─────────────
    # BL-070: write to runtime_dir (workspace when provided, else case_dir)
    out_path = runtime_dir / "extraction_result.json"
    out_path.write_text(
        json.dumps(context.result.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # ── Final summary ─────────────────────────────────────────────────
    total_fields = sum(len(pr.fields) for pr in context.result.periods.values())
    conv_result = next(
        (r for r in context.phase_results if r.phase_name == "ConvertPhase"), None
    )
    conv_diag = conv_result.diagnostics if conv_result else {}
    conv_total = conv_diag.get("total", 0)
    conv_new = conv_diag.get("converted", 0)
    conv_cached = conv_diag.get("skipped", 0)
    conv_failed = conv_diag.get("failed", 0)

    assemble_result = next(
        (r for r in context.phase_results if r.phase_name == "AssemblePhase"), None
    )
    if assemble_result:
        assemble_str = assemble_result.diagnostics.get(
            "truth_pack_path", assemble_result.message
        )
    else:
        assemble_str = "skipped"

    conv_fail_str = f", {conv_failed} failed" if conv_failed else ""
    print(f"\n=== {ticker} Pipeline Complete ===")
    print(f"  Convert:  {conv_total} filings ({conv_new} new, {conv_cached} cached{conv_fail_str})")
    print(f"  Extract:  {total_fields} fields extracted")
    print(f"  Evaluate: {eval_str}")
    print(f"  Assemble: {assemble_str}")
    if _metrics_path:
        print(f"  Metrics:  {_metrics_path.name}")

    return exit_ok, eval_str


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
    sort_by: str = getattr(args, "sort_by", "ticker")
    output_json: str | None = getattr(args, "output_json", None)

    if args.all:
        tickers = sorted(
            d.name for d in CASES_DIR.iterdir()
            if d.is_dir() and (d / "expected.json").exists()
        )
    else:
        tickers = [args.ticker]

    all_ok = True
    reports: list[tuple[str, object]] = []

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
        reports.append((ticker, report))

    # Sort when --all is used and sort_by is specified
    if args.all and sort_by != "ticker":
        if sort_by == "score":
            reports.sort(key=lambda x: x[1].score, reverse=True)
        elif sort_by == "readiness":
            reports.sort(key=lambda x: x[1].readiness_score, reverse=True)

    if output_json:
        artifact_path = Path(output_json).expanduser()
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        payload = build_eval_output_payload([report for _, report in reports])
        artifact_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    for ticker, report in reports:
        status = "PASS" if report.score == 100.0 else "FAIL"
        print(
            f"{ticker}: {status} -- score={report.score}% ({report.matched}/{report.total_expected}) "
            f"readiness={report.readiness_score}% "
            f"[conf={report.validator_confidence_score:.1f} prov={report.provenance_coverage_pct:.1f} penalty={report.extra_penalty:.1f}] "
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


def cmd_onboard(args: argparse.Namespace) -> None:
    """Run onboarding sequence: discover -> [acquire] -> convert -> preflight -> draft."""
    from elsian.onboarding import run_onboarding, render_report_md

    found = _find_case_dir(args.ticker)
    workspace = getattr(args, "workspace", None)

    report = run_onboarding(
        args.ticker,
        case_dir=found,
        with_acquire=getattr(args, "with_acquire", False),
        force_convert=getattr(args, "force", False),
        allow_network_discover=getattr(args, "allow_network_discover", False),
    )

    summary = report["summary"]
    print(f"\n=== Onboarding: {report['canonical_ticker']} ===")
    print(f"  Overall: {summary['overall_status'].upper()}")
    for step_name, step_data in report["steps"].items():
        print(f"  [{step_data['status'].upper():8s}] {step_name}")
    if summary["blockers"]:
        for b in summary["blockers"]:
            print(f"  BLOCKER: {b}")
    if summary["warnings"]:
        for w in summary["warnings"]:
            print(f"  WARNING: {w}")
    print(f"  Next step: {summary['next_step']}")

    if workspace:
        canonical_ticker = report["canonical_ticker"]
        output_dir = Path(workspace) / canonical_ticker
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "onboarding_report.json"
        md_path = output_dir / "onboarding_report.md"
        json_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        md_path.write_text(render_report_md(report), encoding="utf-8")
        print(f"\n  Report saved to {json_path}")

    if summary["overall_status"] == "fatal":
        sys.exit(1)


def _resolve_diagnose_output(output_arg: str | None) -> Path:
    """Resolve the output directory for diagnose reports.

    If *output_arg* is provided, use it (created if absent).
    If not, use a system temporary directory so that the repo tree
    is never mutated by a bare ``elsian diagnose --all`` call.

    Args:
        output_arg: Value of ``--output``, or None.

    Returns:
        Resolved output directory (always exists after this call).
    """
    import tempfile

    if output_arg:
        out = Path(output_arg)
        out.mkdir(parents=True, exist_ok=True)
        return out
    out = Path(tempfile.mkdtemp(prefix="elsian-diagnose-"))
    return out


def cmd_diagnose(args: argparse.Namespace) -> None:
    """Aggregate gaps and hotspots across all cases into a reusable diagnose report."""
    if not getattr(args, "all", False):
        print("--all is required; per-ticker diagnose is not supported yet")
        raise SystemExit(1)

    from elsian.diagnose.engine import build_report
    from elsian.diagnose.render import render_markdown

    output_arg = getattr(args, "output", None)

    report = build_report(CASES_DIR)

    summary = report["summary"]
    print(
        f"Diagnose: {summary['tickers_with_eval']} evaluated, "
        f"{summary['tickers_skipped']} skipped"
    )
    print(
        f"  Overall score: {summary['overall_score_pct']:.1f}% "
        f"({summary['total_matched']}/{summary['total_expected']})"
    )
    print(
        f"  Wrong: {summary['total_wrong']}, "
        f"Missed: {summary['total_missed']}, "
        f"Extra: {summary['total_extra']}"
    )

    hotspots = report.get("hotspots", [])
    if hotspots:
        print(f"\nTop hotspots ({len(hotspots)} total):")
        for h in hotspots[:10]:
            tickers_str = ", ".join(h["affected_tickers"])
            print(
                f"  #{h['rank']} {h['field']} ({h['gap_type']}): "
                f"{h['occurrences']}x [{tickers_str}]"
            )

    # Determine output paths
    out_dir = _resolve_diagnose_output(output_arg)

    json_path = out_dir / "diagnose_report.json"
    md_path = out_dir / "diagnose_report.md"

    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(f"\n  JSON: {json_path}")
    print(f"  MD:   {md_path}")


def cmd_scaffold_task(args: argparse.Namespace) -> None:
    """Generate a task manifest seed with enforced risks, validation plan, and acceptance criteria."""
    from elsian.scaffold import write_task_seed

    risks: list[str] = args.risks or []
    if not risks:
        print("ERROR: --risks is required. Declare at least one risk.")
        sys.exit(1)
    if not args.validation_plan:
        print("ERROR: --validation-plan is required.")
        sys.exit(1)
    if not args.acceptance_criteria:
        print("ERROR: --acceptance-criteria is required.")
        sys.exit(1)
    write_set: list[str] = args.write_set or []
    if not write_set:
        print("ERROR: --write-set is required (at least one file path).")
        sys.exit(1)

    output_dir = Path(args.output) if getattr(args, "output", None) else None

    try:
        manifest_path, notes_path = write_task_seed(
            task_id=args.task_id,
            title=args.title,
            kind=args.kind,
            validation_tier=args.validation_tier,
            write_set=write_set,
            risks=risks,
            validation_plan=args.validation_plan,
            acceptance_criteria=args.acceptance_criteria,
            references=getattr(args, "references", None) or None,
            blocked_surfaces=getattr(args, "blocked_surfaces", None) or None,
            notes=getattr(args, "notes", "") or "",
            force=getattr(args, "force", False),
            output_dir=output_dir,
        )
    except (ValueError, FileExistsError) as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    print(f"Scaffold task: {args.task_id}")
    print(f"  Manifest:  {manifest_path}")
    print(f"  Notes:     {notes_path}")
    print(f"  Risks:     {len(risks)} declared")
    print(f"  Tier:      {args.validation_tier}")
    print(f"  Write set: {len(write_set)} file(s)")


def cmd_scaffold_case(args: argparse.Namespace) -> None:
    """Generate a case seed (case.json + CASE_NOTES.md) for a new ticker."""
    from elsian.scaffold import write_case_seed

    output_dir = Path(args.output) if getattr(args, "output", None) else None
    fiscal_month = getattr(args, "fiscal_year_end_month", None)

    try:
        case_json_path, notes_md_path = write_case_seed(
            ticker=args.ticker,
            source_hint=args.source_hint,
            currency=args.currency,
            period_scope=getattr(args, "period_scope", "ANNUAL_ONLY"),
            exchange=getattr(args, "exchange", None),
            country=getattr(args, "country", None),
            cik=getattr(args, "cik", None),
            fiscal_year_end_month=fiscal_month,
            notes=getattr(args, "notes", "") or "",
            force=getattr(args, "force", False),
            output_dir=output_dir,
        )
    except (ValueError, FileExistsError) as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    ticker_upper = args.ticker.strip().upper()
    print(f"Scaffold case: {ticker_upper}")
    print(f"  case.json:    {case_json_path}")
    print(f"  CASE_NOTES:   {notes_md_path}")
    print(f"  Source:       {args.source_hint}")
    print(f"  Currency:     {args.currency.upper()}")
    print(f"  Period scope: {getattr(args, 'period_scope', 'ANNUAL_ONLY')}")
    print(f"  Next:         review CASE_NOTES.md, then run: elsian acquire {ticker_upper}")


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
    p_run.add_argument(
        "--workspace",
        default=None,
        metavar="PATH",
        help=(
            "Write runtime artifacts (extraction_result.json, run_metrics.json, "
            "truth_pack.json) to PATH/<TICKER>/ instead of cases/<TICKER>/. "
            "cases/ is still read for case.json, expected.json and existing filings/."
        ),
    )
    p_run.set_defaults(func=cmd_run)

    p_eval = sub.add_parser("eval", help="Evaluate extraction vs expected.json")
    p_eval.add_argument("ticker", nargs="?", default="")
    p_eval.add_argument("--all", action="store_true")
    p_eval.add_argument(
        "--sort-by",
        dest="sort_by",
        choices=["ticker", "score", "readiness"],
        default="ticker",
        help="Sort order for --all output (default: ticker)",
    )
    p_eval.add_argument(
        "--output-json",
        dest="output_json",
        default=None,
        metavar="PATH",
        help="Write a machine-readable eval report artifact to this path",
    )
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

    p_diagnose = sub.add_parser(
        "diagnose",
        help="Aggregate gaps and hotspots from existing artifacts into a reusable report",
    )
    p_diagnose.add_argument(
        "--all",
        action="store_true",
        help="Analyze all cases (required flag for this command)",
    )
    p_diagnose.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Write diagnose_report.json and diagnose_report.md to this path",
    )
    p_diagnose.set_defaults(func=cmd_diagnose)

    p_onboard = sub.add_parser(
        "onboard",
        help="Onboarding sequence: discover → [acquire] → convert → preflight → draft",
    )
    p_onboard.add_argument("ticker", help="Ticker symbol (e.g. TZOO, KAR, KAR.AX)")
    p_onboard.add_argument(
        "--with-acquire",
        dest="with_acquire",
        action="store_true",
        help="Run acquire step (requires network)",
    )
    p_onboard.add_argument(
        "--force",
        action="store_true",
        help="Re-convert filings even if .clean.md already exists",
    )
    p_onboard.add_argument(
        "--allow-network-discover",
        dest="allow_network_discover",
        action="store_true",
        help="Allow network calls for discover step when no case.json is found",
    )
    p_onboard.add_argument(
        "--workspace",
        default=None,
        metavar="PATH",
        help=(
            "Write onboarding_report.json and onboarding_report.md to "
            "PATH/<ticker_canónico>/. Pipeline artefacts (case.json, filings, "
            "expected_draft.json) are still written to their standard "
            "case directory."
        ),
    )
    p_onboard.set_defaults(func=cmd_onboard)

    p_scaffold_task = sub.add_parser(
        "scaffold-task",
        help="Generate a task manifest seed enforcing risks, validation plan, and acceptance criteria",
    )
    p_scaffold_task.add_argument("task_id", help="Task ID, e.g. BL-071")
    p_scaffold_task.add_argument("--title", required=True, help="Short human-readable title")
    p_scaffold_task.add_argument(
        "--kind",
        choices=["technical", "governance", "mixed"],
        default="technical",
        help="Task kind (default: technical)",
    )
    p_scaffold_task.add_argument(
        "--validation-tier",
        dest="validation_tier",
        choices=["targeted", "shared-core", "governance-only"],
        default="targeted",
        help="Validation tier (default: targeted)",
    )
    p_scaffold_task.add_argument(
        "--write-set",
        dest="write_set",
        nargs="+",
        metavar="FILE",
        required=True,
        help="Files this task is allowed to write (at least one required)",
    )
    p_scaffold_task.add_argument(
        "--risks",
        nargs="+",
        metavar="RISK",
        required=True,
        help="Declared risks (at least one required — enforced)",
    )
    p_scaffold_task.add_argument(
        "--validation-plan",
        dest="validation_plan",
        required=True,
        help="Validation approach (required — enforced)",
    )
    p_scaffold_task.add_argument(
        "--acceptance-criteria",
        dest="acceptance_criteria",
        required=True,
        help="Closure / acceptance criteria (required — enforced)",
    )
    p_scaffold_task.add_argument("--references", nargs="*", metavar="BL_ID", default=None)
    p_scaffold_task.add_argument("--blocked-surfaces", dest="blocked_surfaces", nargs="*", metavar="PATH", default=None)
    p_scaffold_task.add_argument("--notes", default="", help="Optional free-text notes")
    p_scaffold_task.add_argument("--force", action="store_true", help="Overwrite existing manifest")
    p_scaffold_task.add_argument(
        "--output",
        default=None,
        metavar="DIR",
        help="Write to this directory instead of tasks/",
    )
    p_scaffold_task.set_defaults(func=cmd_scaffold_task)

    p_scaffold_case = sub.add_parser(
        "scaffold-case",
        help="Generate a case seed (case.json + CASE_NOTES.md) for a new ticker",
    )
    p_scaffold_case.add_argument("ticker", help="Ticker symbol, e.g. NEWCO")
    p_scaffold_case.add_argument(
        "--source-hint",
        dest="source_hint",
        required=True,
        help="Filing source: sec, asx, eu, etc.",
    )
    p_scaffold_case.add_argument(
        "--currency",
        required=True,
        help="ISO currency code, e.g. USD, AUD, EUR",
    )
    p_scaffold_case.add_argument(
        "--period-scope",
        dest="period_scope",
        choices=["ANNUAL_ONLY", "FULL"],
        default="ANNUAL_ONLY",
        help="Period scope (default: ANNUAL_ONLY)",
    )
    p_scaffold_case.add_argument("--exchange", default=None, help="Exchange name, e.g. NASDAQ")
    p_scaffold_case.add_argument("--country", default=None, help="ISO country code, e.g. US")
    p_scaffold_case.add_argument("--cik", default=None, help="SEC CIK or equivalent regulator ID")
    p_scaffold_case.add_argument(
        "--fiscal-year-end-month",
        dest="fiscal_year_end_month",
        type=int,
        default=None,
        metavar="MONTH",
        help="Fiscal year end month 1-12 (default: 12)",
    )
    p_scaffold_case.add_argument("--notes", default="", help="Optional free-text notes")
    p_scaffold_case.add_argument("--force", action="store_true", help="Overwrite existing case.json")
    p_scaffold_case.add_argument(
        "--output",
        default=None,
        metavar="DIR",
        help="Write to DIR/<TICKER>/ instead of cases/<TICKER>/",
    )
    p_scaffold_case.set_defaults(func=cmd_scaffold_case)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
