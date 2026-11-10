# InvestFlow — 06 · Gap Analysis

| | |
|---|---|
| **Status** | Rolling document — reviewed at the end of **every** iteration ([07-iterative-prompts](07-iterative-prompts.md) §2) |
| **Last updated** | 2026-11-10 (ITER-22 close review: no new gaps; FR-IMP-1 AC-IMP1a–IMP1g covered at L1/L2/L3/L4, AC-IMP1h slipped → ITER-23 by pre-agreement, tracked as a scope delta not a gap) |

Gap analysis compares three layers and records what does (not) survive between them:

1. **Wants** — the user's original feature list + session decisions ([00 §2](00-overview.md))
2. **Spec** — what [01-requirements](01-requirements.md) actually commits to, and [02-architecture](02-architecture.md) can build ([roadmap 04 §2](04-progress.md))
3. **Reality** — what each iteration's tests prove at close-of-iteration

## 2. Initial known gaps (scoping decisions taken at time zero)

### 2.1 Deliberately dropped / deferred

| ID | Original ask | Gap type | Handling | Reference |
|---|---|---|---|---|
| **G-001** | "Budget" reporting (budget vs actual; budgets were explicitly in original feature list) | **Dropped by decision D-06** | No budget entities exist in the model. Any future re-introduction requires: new `budgets`/`budget_lines` tables, budget-v variance report kind, dashboard card, settings affect… no current code needs reshaping since reports read from `transaction_lines` | [00 D-06](00-overview.md), [01 §13](01-requirements.md) |
| **G-002** | FIFO/tax-lot cost basis | **Deferred** (avg cost chosen, D-09) | `positions` stores avg cost only; lots need: transactions→lots link table, per-lot sale matching, new P&L report. Deferred without blocking v1 average-cost design | [00 D-09](00-overview.md), [01 AC-I1](01-requirements.md) |
| **G-003** | Multi-currency / FX | **Dropped** (D-05, single currency) | Money type is single-currency cents; adding multi-currency would touch nearly every table (currency col + rate caching + reporting conversion). Decision consciously avoids this for v1 | [00 D-05](00-overview.md) |
| **G-004** | Role-based permission granularity (admin/analyst) | **Dropped** (D-03 single role) | Guards check only authentication, not role; if roles arrive later, add `role` col + permission map + guard matrix re-tests | [01 FR-U](01-requirements.md) |
| **G-005** | Non-financial manual assets (home, car) in net worth | **Dropped** (user chose assets+holdings−liabilities) | Net worth engine sums only ledger accounts + positions; manual asset cards would need a `manual_assets` table + valuation dates | [01 FR-R6/NetWorth](01-requirements.md) |
| **G-006** | FastAPI+Next.js—local app desktop packaging | **Dropped for v1** (D-01 local web) | Electron/Tauri wrapper postponed; the API remains shell-independent so a wrapper can paste-bake later without backend change | [02 §1](02-architecture.md) |
| **G-007** | CSV import of statements / broker history | **Deferred by decision** — superseded by **FEAT-001** in the backlog as the working record | Working record: [08-backlog FEAT-001](08-backlog.md) (positions + transactions CSV, dry-run wizard, dedupe). If added: importer service + mapping templates + duplicate detection; blocks nothing in v1 | [01 FR-T/I](01-requirements.md) |

### 2.2 Known-risk design gaps (accepted, with mitigations)

| ID | Risk gap | Why accepted | Mitigation in place |
|---|---|---|---|
| R-01 | **Yahoo unofficial endpoints**: no SLA, may change without notice, rate limits | Free & requested (D-10) | Provider ABC isolates failure surface; stale-price badge + manual fallback keep app fully usable (AC-I2b/c); cache absorbs outages | 
| R-02 | SQLite concurrent-write contention if two browser tabs post simultaneously | single-household scale | WAL + busy_timeout + single write txn per request; perf tests (NFR-4) run simulated concurrent writers; document "one writer tab at a time" in README (edge platform limitation) |
| R-03 | Only e2e-limited a11y coverage for heavy chart screens (charts are canvas/svg) | v1 timeline | Manual a11y spot-checks + keyboard shortcuts on the *tables* (chart data dual-rendered as accessible table per NFR-7); full a11y audit deferred to ITER-16 |
| R-04 | No automated restore-from-backup (AC-S6 defines download-only) | Restore implies destructive replacement; risky to automate early without a maintenance session | Manual restore runbook in README + remove/verify script in Makefile; revisit after ITER-16 with a decision ADR |
| R-05 | Optimizer on short/window histories can be numerically brittle (ill-conditioned covariance) | mean-variance was the requested scope (D-14) | ≥120-day gate (AC-I7c), explicit infeasibility wording (AC-I7b), unit tests on known-answer problems; shrinkage estimator noted as future improvement |
| R-06 | Threshold dependencies on external universe (positions priced while broker slept) for net-worth series accuracy | valuation is at-read-time (ADR-002) | Price-cache persists daily close; net worth recomputation is deterministic from cached close, so past values don't drift when quotes refresh (cache is write-once per date) |

### 2.3 Conservative extrapolations flagged for review (compare against wants during iteration review)

| ID | Topic | Concern | Proposed verification point |
|---|---|---|---|
| X-01 | **"Simple transaction management"** vs full double-entry UI with split-lines and transfers | user may find the advanced editor overkill → confirm at ITER-07 review | ITER-07 close |
| X-02 | **Mega menu** has 6 groups (more than a minimal app) | confirm grouping/order satisfaction after ITER-05 | ITER-05 close review |
| X-03 | Yahoo news coverage is thin for illiquid tickers (pink-sheet ADRs etc.) | confirm acceptable at ITER-14 | review news quality; record decision in ADR-log |
| X-04 | Currency display / rounding per locale (round-half-up default) matches bookkeeping conventions | UI default value should be user-confirmed | ITER-16 settings review |

## 3. Living gap register (opened during iterations)

Append rows during development; never delete (mark superseded). Format:

```
### GAP-NNN — <title>
- **Opened:** YYYY-MM-DD (ITER-XX) · **Type:** dropped / deferred / discovered-missing / discovered-de-scope
- **Origin:** source ref (AC id, user feedback, defect, review row)
- **Description:** what is missing, observable impact on users
- **If deferred:** target iteration + any prerequisite decisions/ADRs
- **If dropped:** why acceptable; what would be needed if revisited later
- **Status:** open → scheduled → included (target iter) → closed / superseded (→ link)
```

*(register is live — do not pre-populate with speculative entries; new examples will follow ADR/log conventions in [04 §4](04-progress.md).)*

### GAP-008 — Coverage enforcement not yet wired (pytest-cov gate / vitest coverage provider)
- **Opened:** 2026-11-08 (ITER-01) · **Type:** discovered-missing
- **Origin:** [03 §6](03-test-plan.md) NFR-6 coverage targets vs ITER-01 reality
- **Description:** backend pytest runs with `pytest-cov` available but no `fail-under` gate; frontend vitest has **no coverage provider installed** (`@vitest/coverage-v8` absent). Measured manually in ITER-01: backend 100% / frontend not measured.
- **If deferred:** target ITER-02 — wire `fail_under=85` (later revision-section targets from 03 §6) + install `@vitest/coverage-v8` with `coverage.thresholds` as first logic-bearing code lands, so gates are exercised while the suite is small.
- **Status:** open → scheduled (ITER-02) → closed (ITER-02: `backend/pyproject.toml` enforces `--cov-fail-under=85`; frontend installs `@vitest/coverage-v8` and wires provider in `frontend/vitest.config.ts`)

## 4. Close-of-iteration checklist (gap-analysis part)

At each iteration close ([07 §2](07-iterative-prompts.md)):

1. Diff *spec* vs *implementation*: any AC untested/unimplemented → new GAP row (type discovered-missing) **or** defect if it was previously Done.
2. Review §3 register: promote rows with ready prerequisites to "scheduled (ITER-XX)".
3. Confirm that §2 table entries untouched during the iteration are still accurate.
4. Refresh the 3-layer picture (§1) status sentence below: *(update on close)* —
   **Wants are fully spec'd (§2.1/§2.2 records deltas), Reality has 22 iteration rows done — ITER-01 through ITER-22 (✅ 2026-11-10):
   the portfolio CSV import slice (FR-IMP-1) is now covered at L1 (`backend/tests/unit/test_importer_core.py`), L2 (`backend/tests/api/test_imports.py`), L3 (`frontend/app/__tests__/import-page.test.tsx` + mega-menu Import item) and L4 (import wizard scenario in `e2e/smoke.spec.ts`); the AC-IMP1h price-history stretch slipped to ITER-23 by pre-agreement (scope delta, tracked in [01 §12](01-requirements.md) + [08 §3C](08-backlog.md), not a gap); the backlog's trade-leg wording was refined by ADR-008 (positions-only buys/sells, real postings for dividend/fee) rather than left as a doc-vs-reality contradiction; no new open gaps were introduced in ITER-22.**
