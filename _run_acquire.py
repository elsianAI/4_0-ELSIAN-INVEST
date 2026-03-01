"""Run KAR acquisition via AsxFetcher."""
import logging
import json
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format="%(name)s - %(message)s",
    stream=sys.stderr,
)
# Silence noisy libraries
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("pdfminer").setLevel(logging.WARNING)

from elsian.acquire.asx import AsxFetcher
from elsian.models.case import CaseConfig

case = CaseConfig.from_file("cases/KAR")
fetcher = AsxFetcher()
result = fetcher.acquire(case)

print("=== RESULT ===")
print(f"Downloaded: {result.filings_downloaded}")
print(f"Failed: {result.filings_failed}")
print(f"Coverage: {result.filings_coverage_pct}%")
if result.coverage:
    print(json.dumps(result.coverage, indent=2))
print(f"Notes: {result.notes}")
