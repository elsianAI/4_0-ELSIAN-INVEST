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

    p_dash = sub.add_parser("dashboard", help="Summary table of all cases")
    p_dash.set_defaults(func=cmd_dashboard)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
