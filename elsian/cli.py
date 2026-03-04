"""CLI entry point for ELSIAN 4.0."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

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


def _get_fetcher(case: CaseConfig):
    """Return the appropriate fetcher for a case."""
    hint = case.source_hint.lower()
    if hint in ("sec", "sec_edgar"):
        from elsian.acquire.sec_edgar import SecEdgarFetcher
        return SecEdgarFetcher()
    elif hint in ("asx",):
        from elsian.acquire.asx import AsxFetcher
        return AsxFetcher()
    elif hint in ("eu", "eu_manual", "manual_http"):
        from elsian.acquire.eu_regulators import EuRegulatorsFetcher
        return EuRegulatorsFetcher()
    else:
        from elsian.acquire.manual import ManualFetcher
        return ManualFetcher()


def cmd_acquire(args: argparse.Namespace) -> None:
    """Download filings for a ticker."""
    case_dir = _find_case_dir(args.ticker)
    if not case_dir:
        print(f"Case not found: {args.ticker}")
        sys.exit(1)

    case = CaseConfig.from_file(case_dir)
    fetcher = _get_fetcher(case)

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


def cmd_run(args: argparse.Namespace) -> None:
    """Run full pipeline: extract + eval via Pipeline orchestrator."""
    from elsian.extract.phase import ExtractPhase
    from elsian.evaluate.phase import EvaluatePhase
    from elsian.pipeline import Pipeline
    from elsian.context import PipelineContext

    case_dir = _find_case_dir(args.ticker)
    if not case_dir:
        print(f"Case not found: {args.ticker}")
        sys.exit(1)

    case = CaseConfig.from_file(case_dir)
    context = PipelineContext(case=case, config_dir=str(case_dir.parent.parent / "config"))

    phases = [ExtractPhase(), EvaluatePhase()]
    pipeline = Pipeline(phases)
    context = pipeline.run(context)

    # Save extraction result
    out_path = case_dir / "extraction_result.json"
    out_path.write_text(
        json.dumps(context.result.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Print phase results
    for error in context.errors:
        print(f"  ERROR: {error}")

    total_fields = sum(len(pr.fields) for pr in context.result.periods.values())
    print(
        f"{args.ticker}: extracted {total_fields} fields across "
        f"{len(context.result.periods)} periods from {context.result.filings_used} filings"
    )

    expected_path = case_dir / "expected.json"
    if expected_path.exists():
        report = evaluate(context.result, str(expected_path))
        status = "PASS" if report.score == 100.0 else "FAIL"
        print(
            f"  Eval: {status} -- {report.score}% ({report.matched}/{report.total_expected}) "
            f"wrong={report.wrong} missed={report.missed} extra={report.extra}"
        )
        if report.score < 100.0:
            for d in report.details:
                if d.status != "matched":
                    print(f"    {d.status} {d.period}/{d.field_name} exp={d.expected} got={d.actual}")
            sys.exit(1)
    else:
        print("  No expected.json — skipping evaluation")


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
    """Generate expected_draft.json from iXBRL data in .htm filings."""
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
        # Generate skeleton for tickers without iXBRL files
        print(f"{args.ticker}: No iXBRL (.htm) files found. Generating skeleton.")
        skeleton = {
            "version": "1.0",
            "ticker": case.ticker or args.ticker,
            "currency": case.currency,
            "scale": "mixed",
            "scale_notes": "SKELETON — no iXBRL files available. Curate manually from PDF/other sources.",
            "_generated_by": "elsian curate (skeleton)",
            "periods": {},
        }
        out_path = case_dir / "expected_draft.json"
        out_path.write_text(
            json.dumps(skeleton, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  Saved skeleton to {out_path}")
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
        _compare_draft_vs_expected(draft, expected)

    print(f"  Saved to {out_path}")


def _compare_draft_vs_expected(
    draft: dict,
    expected: dict,
) -> None:
    """Print comparison of draft vs existing expected.json."""
    exp_periods = expected.get("periods", {})
    draft_periods = draft.get("periods", {})

    common_periods = set(exp_periods.keys()) & set(draft_periods.keys())
    if not common_periods:
        print("  Coverage: no overlapping periods with expected.json")
        return

    total_exp = 0
    covered = 0
    matched = 0
    for plabel in sorted(common_periods):
        exp_fields = exp_periods[plabel].get("fields", {})
        draft_fields = draft_periods[plabel].get("fields", {})
        for fname, fdata in exp_fields.items():
            total_exp += 1
            if fname in draft_fields:
                covered += 1
                exp_val = fdata.get("value")
                draft_val = draft_fields[fname].get("value")
                if exp_val is not None and draft_val is not None:
                    if exp_val == 0:
                        if draft_val == 0:
                            matched += 1
                    elif abs(exp_val - draft_val) / abs(exp_val) <= 0.01:
                        matched += 1

    cov_pct = (covered / total_exp * 100) if total_exp else 0
    match_pct = (matched / total_exp * 100) if total_exp else 0
    print(
        f"  vs expected.json ({len(common_periods)} common periods): "
        f"coverage={covered}/{total_exp} ({cov_pct:.0f}%), "
        f"value_match={matched}/{total_exp} ({match_pct:.0f}%)"
    )


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

    p_run = sub.add_parser("run", help="Full pipeline: extract + eval")
    p_run.add_argument("ticker")
    p_run.set_defaults(func=cmd_run)

    p_eval = sub.add_parser("eval", help="Evaluate extraction vs expected.json")
    p_eval.add_argument("ticker", nargs="?", default="")
    p_eval.add_argument("--all", action="store_true")
    p_eval.set_defaults(func=cmd_eval)

    p_curate = sub.add_parser("curate", help="Generate expected_draft.json from iXBRL")
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

    p_coverage = sub.add_parser("coverage", help="Audit filing coverage for a ticker or all")
    p_coverage.add_argument("ticker", nargs="?", default="")
    p_coverage.add_argument("--all", action="store_true")
    p_coverage.set_defaults(func=cmd_coverage)

    p_dash = sub.add_parser("dashboard", help="Summary table of all cases")
    p_dash.set_defaults(func=cmd_dashboard)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
