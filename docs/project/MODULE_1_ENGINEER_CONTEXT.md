# ELSIAN 4.0 — Module 1 Engineer Context

> Technical manual for the active extraction module.
> Read this after `VISION.md`, `docs/project/ROLES.md`, and `docs/project/KNOWLEDGE_BASE.md`.
> This document owns Module 1 technical doctrine. It does not redefine role contracts, routing, gates, or governance.

## 1. Active module

Module 1 is the deterministic financial extraction pipeline.

Active flow:

`Acquire -> Convert -> Extract -> Normalize -> Merge -> Evaluate`

### Phase responsibilities

- **Acquire**: obtain filings and source artifacts from the correct fetcher or manifest.
  For `eu_manual` / IR-only cases, prefer deterministic discovery through the existing fetcher path before normalizing permanent `filings_sources`.
- **Convert**: transform raw filings into clean, parseable inputs.
- **Extract**: produce field candidates from iXBRL, HTML tables, PDF tables, or narrative patterns.
- **Normalize**: resolve canonical fields, units, signs, and provenance.
- **Merge**: select the best candidate across filings and sources.
- **Evaluate**: compare against expected truth and regression baselines.

Future modules may exist in `VISION.md`, but they are deferred and out of scope for this manual.

## 2. Class and phase model

Every phase is a typed class. The pipeline is composed, not hardcoded.

- `PipelinePhase`: base contract for pipeline phases.
- `Fetcher`: base contract for acquisition strategies.
- `Extractor`: base contract for extraction strategies.
- `Pipeline`: lightweight orchestrator; chains phases and carries context.
- `PipelineContext`: shared state for provenance, audit, and confidence.

### Design principles

- One class per phase with clear input/output boundaries.
- Multiple implementations per phase; new market or extractor means new class, not new branching.
- Pipeline orchestration contains no business logic.
- Configuration over code for aliases, priorities, and selection rules.
- Regression protection is part of the design, not an afterthought.

## 3. Provenance requirements

Every extracted value must carry useful provenance.

### Minimum expectation

- `source_filing`

### Strong expectation

- table identity
- row and column identity
- original raw text
- extraction method

### Level model

- **Level 1**: filing source only
- **Level 2**: coordinates inside the normalized document
- **Level 3**: link back to the original HTML/PDF position

### Current implementation note

- The current Level 3 pilot is a post-extraction artifact, not a new extractor.
- `elsian source-map {TICKER}` builds `source_map.json` from `extraction_result.json`.
- The CLI reports `FULL`, `PARTIAL`, or `EMPTY` resolution explicitly; missing `extraction_result.json` is a user-facing precondition error, not a traceback path.
- In the current pilot, deterministic anchors on equivalent normalized artifacts
  (`.clean.md`, `.txt`) count as valid click targets as long as the original
  filing path is still preserved in the artifact.
- Level 3 must not change extraction winners, merge logic, or TruthPack schema.

### Rule

Do not extract values without provenance coordinates when the extractor can provide them. Provenance is part of the data contract, not optional metadata.

## 4. Sign convention

Policy: store values **as presented on the face of the statement**, with the project’s normalization rules.

### Income statement

- Revenue and gross profit are positive.
- Expense lines such as `cost_of_revenue`, `research_and_development`, `sga`, `depreciation_amortization`, `interest_expense`, and usually `income_tax` are stored as positive costs.
- `ebit`, `ebitda`, and `net_income` carry profit/loss sign.
- EPS follows `net_income`.

### Balance sheet

- `total_assets`, `total_liabilities`, `cash_and_equivalents`, and `total_debt` are positive.
- `total_equity` can be negative only in genuine deficit situations.

### Cash flow

- `cfo`: positive for “provided by”, negative for “used in”.
- `capex`: always negative.
- `fcf`: follows reported sign.

### Trap

Parentheses in many 20-F and IFRS filings are formatting, not necessarily negative meaning. Do not flip signs mechanically.

## 5. Restatement policy

Policy: **as reported unless explicit restatement**.

- Use the primary filing for that fiscal period by default.
- Only replace with a later value when the filing contains explicit restatement evidence such as `restated`, `as revised`, `as corrected`, or `reclassified`.
- No explicit trigger means no restatement.
- When a restatement is applied, document trigger, evidence text, restating filing, original filing, and original value.

## 6. Canonical fields

### Income statement

- `ingresos`
- `cost_of_revenue`
- `gross_profit`
- `ebitda`
- `ebit`
- `net_income`
- `eps_basic`
- `eps_diluted`
- `research_and_development`
- `sga`
- `depreciation_amortization`
- `interest_expense`
- `income_tax`

### Balance sheet

- `total_assets`
- `total_liabilities`
- `total_equity`
- `cash_and_equivalents`
- `accounts_receivable`
- `inventories`
- `accounts_payable`
- `total_debt`

### Cash flow

- `cfo`
- `capex`
- `fcf`

### Per-share / shares

- `dividends_per_share`
- `shares_outstanding`

Aliases belong in config and map into these canonical names only.

## 7. Ground truth and period scope

`expected.json` is curated truth, not pipeline output.

### Core rules

- Never weaken `expected.json` to match a pipeline bug.
- `elsian curate` is only a draft generator: use iXBRL where available and deterministic PDF/text extraction otherwise, but never treat `expected_draft.json` as ground truth without review.
- Never calculate derived fields unless the filing explicitly reports them.
- Omit truly absent fields rather than writing fake zeroes.
- Use real evidence from the filing for every expected value.

### Period naming

- Annual: `FY2024`
- Quarterly: `Q1-2024`, `Q2-2024`, `Q3-2024`, `Q4-2024`
- Semi-annual: `H1-2024`, `H2-2024`

### Period scope progression

- `ANNUAL_ONLY` first for all new tickers.
- Promote to `FULL` only after annual periods are at 100%.
- `period_scope` in `case.json` must match what exists in `expected.json`.

### Scale rules

- Store values in the unit the filing shows.
- Do not scale to absolute units.
- Keep `scale` and `scale_notes` accurate.

### Common traps

- `net_income` is not EPS.
- `total_liabilities` is not “liabilities and equity”.
- `cash_and_equivalents` is not “cash plus restricted cash”.
- Prefer weighted average basic shares over diluted shares for `shares_outstanding`.

## 8. PDF extraction policy

### Current standard

- `pdfplumber` with layout-aware extraction is the project standard for PDF tables.

### Rejected default

- PyMuPDF is not the primary PDF table extractor because of kerning and number-splitting issues on financial documents.

### Future note

- Learned table models such as Table Transformer are future options, not current doctrine.

## 9. Porting guidance from 3.0 (`DEC-009`)

Port validated knowledge first; do not reinvent unless the old approach is proven insufficient.

### Port these

- aliases, scale cascade, selection rules
- fetchers and crawling logic that are already validated
- iXBRL extraction logic
- HTML table extraction logic
- evaluation framework and expected structure
- validated test cases and regression expectations

### Do not port blindly

- monolithic orchestration layers
- engine/runners coupling
- code without tests or traceability
- product or analysis layers outside Module 1

## 10. Regression and troubleshooting guidance

### Reference regression cases

- `TZOO`: FULL reference implementation
- `GCT`, `IOSP`, `NEXN`, `SONO`, `TEP`, `TALO`: validated annual references
- `KAR`: non-US PDF-heavy market coverage

### Recurring failure patterns

- fiscal vs calendar quarter mismatch
- generic aliases defeating better labels
- component line defeating total line
- working-capital movement rows beating ending-balance rows
- rescaled iXBRL values beating exact values
- local selection or sort fixes causing cross-ticker regressions

### If X fails, look at Y

- `coverage` -> fetcher path, manifests, source hints
- period mismatch -> expected truth vs fiscal/calendar labeling
- missing cash flow identity fields -> field dependency matrix, aliases, validator
- wrong working-capital ending balance -> balance sheet rows, movement-table penalties, primary-filing preference
- bad PDF values -> PDF tables, extract phase wiring, units hints, reject patterns
- incomplete provenance -> field model and extractor creation points
- one ticker improves and others regress -> aliases, selection rules, merge, compare against last green sweep

## 11. Ticker onboarding checklist

When adding a ticker, treat it as a pipeline capability test.

1. Create a correct `case.json`.
2. Acquire filings through the pipeline.
3. If acquisition fails because the market is unsupported, build or adapt the fetcher rather than normalizing manual work. For LSE/AIM-style IR websites, prefer a conservative crawler improvement that can recover a minimal stable document set before falling back to hardcoded URLs.
4. Verify the filing quality and presence of core statements.
5. Curate `expected.json` from filings as truth.
6. Start in `ANNUAL_ONLY`.
7. Fix the pipeline or document genuine gaps; do not fake the score.
8. Run regression and check for collateral damage.
9. Promote to `FULL` only after annual extraction is stable.

## 12. Use of this document

- Engineers use it as the technical manual for Module 1 work.
- Auditors use it when auditing Module 1 changes, so they can judge technical invariants without guessing.
- Update it when a real code change establishes or invalidates stable Module 1 doctrine.
- Do not move role contracts, routing, gates, or governance rules here; those belong in `docs/project/ROLES.md`.
