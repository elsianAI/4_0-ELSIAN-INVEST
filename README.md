# ELSIAN 4.0 -- Financial Data Extraction Platform

Commercial-grade financial data extraction with full provenance tracing.

## Quick Start

```bash
# Install
pip3 install -e ".[dev]"

# Run tests
python3 -m pytest tests/ -v

# Evaluate a ticker
python3 -m elsian eval TZOO

# Evaluate all tickers (regression)
python3 -m elsian eval --all

# Dashboard
python3 -m elsian dashboard
```

## Architecture

```
Layer 0 -- Sources      (Fetchers: SEC EDGAR, ESEF, IR Crawler, Manual)
Layer 1 -- Extraction   (iXBRL, HTML Tables, PDF Tables, Narrative)
Layer 2 -- Qualitative  (LLM-assisted, future)
Layer 3 -- LLM Fallback (future)
Layer 4 -- Analysis     (TruthPack, CATALYST, BULL, future)
```

Every extracted value carries **provenance** -- tracing the number back to the
exact cell in the original filing.

## Bootstrap Status

- [x] Step 1: Scaffold
- [x] Step 2: Models (with Provenance)
- [x] Step 3: Configuration (field_aliases, selection_rules)
- [x] Step 4: Base classes (Fetcher, Extractor, PipelinePhase ABCs)
- [x] Step 5: Normalize (AliasResolver, ScaleCascade, SignConvention, AuditLog)
- [x] Step 6: Evaluate (evaluator + dashboard)
- [x] Step 7: CLI (eval, dashboard)
- [ ] Step 8: First Extractor (HtmlTableExtractor)
- [ ] Step 9: First Fetcher (SecEdgarFetcher)
- [ ] Step 10: Port all test cases (regression suite)
