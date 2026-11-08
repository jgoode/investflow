# InvestFlow — 08 · Backlog

| | |
|---|---|
| **Status** | Living document — reviewed at the end of **every** iteration ([07-iterative-prompts](07-iterative-prompts.md) §2, step R8) |
| **Last updated** | 2026-11-08 |

## 1. Purpose

The backlog documents **future feature requests** and **deferred work** that are out of scope for the
current 16-iteration roadmap ([04-progress](04-progress.md) §2), with enough specification detail that
they can be scheduled later without re-deriving context. Items here must **not** block, or drift into,
iterations unless they are formally moved onto the roadmap.

### 1.1 Lifecycle

```
candidate → specified (this doc, full §3 outline) → scheduled (target iteration set in 04 §2)
          → included (its iteration runs; this doc row updated) → closed (shipped)
```

Rules:

1. A backlog item never enters an iteration implicitly; §4 of [07-iterative-prompts](07-iterative-prompts.md)
   can only reference ACs from [01-requirements](01-requirements.md). When an item is selected for
   implementation, its pending requirements are **promoted into** `01-requirements.md` as new FR/AC ids
   (with an ADR row in [04 §4](04-progress.md)) — the backlog row then links to them.
2. Each item has exactly one owner-of-truth. Deferred *concepts* recorded in
   [06-gap-analysis](06-gap-analysis.md) stay there for the scope-diff view; the backlog is the working
   list and links back.
3. Prioritization is the user's call (interactive session), not the agent's.

## 2. Backlog index

| ID | Title | Type | Origin | Size | Status |
|---|---|---|---|---|---|
| **FEAT-001** | Portfolio CSV import (positions + transactions) | Future feature request | User request 2026-11-08 | M (≈1–2 iterations) | specified — Q&A resolved (§3.7) |
| **FEAT-002** | Non-investment opening balances + statement migration import (CSV) | Future feature request | User request 2026-11-08 (extends FEAT-001 scoping note §3.5) | M (≈1–2 iterations, shared importer core) | specified — Q&A resolved (§3A.6) |
| — | *(related, owned in [06-gap-analysis](06-gap-analysis.md):* G-001 budgets · G-002 FIFO lots · G-004 role granularity · G-005 manual assets · G-006 desktop packaging | items | session decisions | — | recorded-at-time-zero |

## 3. Feature request FEAT-001 — Portfolio CSV import

> **Status: specified, unscheduled (status per §2). Nothing below is implemented; it is a design sketch
> to be promoted into the requirements when scheduled.**

### 3.1 Summary

Support importing **portfolio positions** and **portfolio transactions** for brokerage/investment accounts
from **CSV files**, so that holdings and their buy/sell history can be established in bulk instead of
entered one-by-one (complements screen-level flows FR-I1 / [01 §5](01-requirements.md) AC-I1a–I1d).

Two distinct CSV flavors in one feature:

1. **Positions import** — a current-holdings snapshot sheet: per account + ticker: quantity, avg cost
   (or total cost), option price/as-of. Imports create/replace positions (AC-style: bulk-set average-cost
   seeds without individual buy transactions). *(Q-2 resolved: replace-with-flag.)*
2. **Transactions import** — a ledger-sheet of trades: date, type (buy/sell/dividend/fee), ticker,
   quantity, price, fee, cash account. Imports post real double-entry transactions through the existing
   posting service (invariant T-1) and feed the average-cost engine. Dividend/fee rows are **included**
   in the scheduled form *(Q-3)*.
3. **Price history import (confirmed stretch, Q-3)** — daily close/volume CSV feeding `price_cache`
   with `source='manual'`, subject to the manual-price precedence rules already documented for
   AC-I2c.

### 3.2 User stories

- US-1 — As a user switching from another app/broker, I want to import my current holdings so the net-worth dashboard is correct on day one.
- US-2 — As the same user, I want to import my trade history so realized/unrealized P&L and the avg-cost engine match my broker.
- US-3 — Near-miss safety: I want a **dry-run preview with row-level errors** and no partial import — all rows valid or nothing posted (atomic per file).
- US-4 — Re-import handling: I want to know rows I re-import won't double-post (idempotency story, §3.6).

### 3.3 Functional sketch (to promote into FR/ACs at scheduling)

| Area | Provisional behavior |
|---|---|
| Source files | UTF-8 CSV with header row; column mapping via a UI wizard (drag field → column), saved **mapping templates** per broker name; template library shipped with 2–3 starter mappings |
| Validation | Schema check (types, iso dates, ticker uppercase), per-row validation, row-level error report (downloadable CSV of failure rows); quantity > 0, amount integer-cents conversion; ticker auto-creates `positions` target only when a matching account is mapped |
| Accounts binding | Importer requires explicit mapping of each CSV account column value → existing InvestFlow **brokerage account** (with a "create account now" affordance, gated on FR-C rules); no silently auto-created accounts |
| Duplicate detection | Positions: file row **replaces** the account's existing open positions by `(account, ticker)`; holdings absent from the file are flagged in preview for explicit confirmation (closed positions keep realized P&L). Transactions: hash-tuple dedupe (date/ticker/type/qty/price/fee/cash-account) matched against existing postings; matches are skipped and reported — never double-posted |
| Dry-run | Every import runs in *preview mode* showing: parsed rows, would-post transactions preview (amounts + legs), duplicate-skip list, total cash movement sanity check; import only on confirm |
| Atomicity | Every import (including price history) is one transaction; any hard row error aborts everything (US-3); soft rows (duplicates) are skipped not failed |
| Size/limits (Q-4) | Synchronous processing only; file ≤ 5 MB and ≤ 5,000 rows per import; larger inputs refused at upload with a split-file suggestion; no background-job infra |
| Templates (Q-5) | Starter mapping templates shipped: *positions snapshot*, *trade history*, *bank statement*; user-defined mappings saveable alongside |
| Avg-cost interplay | Positions set avg cost directly (with a warning linking lots semantics). Trade history must arrive **in date order per (account, ticker)** — the importer enforces replay ordering and rejects out-of-order sell-before-buy rows with clear errors |
| Reporting impact | After an import, dashboards/reports reflect imported state; audit log records `import.positions` / `import.transactions` (entity = file import id, row counts) per `audit_log` design in [02 §3.1](02-architecture.md) |

### 3.4 Architectural impact

- New tables: `import_mappings(name, columns_json, created_by)`, `import_batches(id, kind, file_ref, status, counts_json, created_at/…)` (lightweight staging: raw CSV is **not** persisted wholesale by default — only counts + failure rows).
- New service: `services/importer/` (parsers, mapping resolver, dry-run evaluator, post-through-posting-service — never writes `transaction_lines` directly, preserving ledger invariants).
- Frontend: a single **Import center** `/investments/import` (Q-10) with tabs *Portfolio* and *Statements & Balances*: account mapping → column mapping → preview → confirm → result report; wired into the Investments mega-menu group.
- New Make/script targets: `make seed-import-templates` optional; tests at L1 (parser/dedupe math), L2 (atomic import via API), L4 (wizard E2E with fixture files).

### 3.5 Explicit non-goals for FEAT-001

- No PDF/OFX/QIF/broker-API statement ingestion (CSV only).
- No auto-creation of accounts/categories beyond explicit user affirmation in the wizard.
- No ordering fix-up for garbage data (e.g., sells before buys) — reject with row error.
- No multi-currency ([06 G-003](06-gap-analysis.md)); CSV amounts assume book currency.
- **Migration-tool status**: superseded by FEAT-002 — the pair (FEAT-001 + FEAT-002) is the full
  "migrate from my previous app / bank statements" path; FEAT-001 alone covers only the investment side
  ([08 §3A](08-backlog.md)).

### 3.6 Open questions (answered 2026-11-08 — resolutions in §3.7)

Answered in the 2026-11-08 backlog Q&A session — see §3.7.

| Q# | Question | Affects |
|---|---|---|
| Q-1 | Is dedupe-by-hash the desired re-import behavior, or "no dedupe, refuse exact duplicates with row errors"? | §3.3 dup handling |
| Q-2 | Should positions import replace the account's existing positions or merge (warn-only on qty mismatch)? | §3.3, audit trail |
| Q-3 | Stretch order-scoped extras: price-history CSV, dividends-as-transactions mapping — in or out of the scheduled form? | scope size/counts |
| Q-4 | Max file size / row count for the import UI (sync API vs background job)? | architecture impact |
| Q-5 | Which "starter mapping templates" are wanted by name (broker-specific examples)? | template library |

### 3.7 Q&A record (2026-11-08 backlog session)

Answers are binding design input; they are promoted into `01-requirements.md` FR/AC ids only when the
feature is scheduled ([§4 Maintenance](#4-maintenance)).

| Q# | Answer | Resolved to |
|---|---|---|
| Q-1 | Skip duplicates | Hash-tuple `(date/ticker/type/qty/price/fee/cash-account)` matched against existing postings; identical rows skipped and listed in a dedupe report during preview |
| Q-2 | Replace + flag | Imported snapshot replaces the account's existing open positions; absent holdings are flagged in preview for explicit confirmation; closed positions keep their realized P&L |
| Q-3 | Extras included | Scheduled form covers positions + trade transactions (buy/sell/dividend/fee rows), **and** price-history CSV feeding `price_cache` with `source='manual'` |
| Q-4 | Sync with limits | Synchronous processing; limits ≤ **5 MB file / ≤ 5,000 rows**; larger files refused with a split-file suggestion; no background-job infrastructure in either feature |
| Q-5 | Generic templates | Three shipped starters: *positions snapshot*, *trade history*, *bank statement*; broker-specific quirks handled in the mapping wizard |

---

## 3A. Feature request FEAT-002 — Non-investment opening balances + statement migration import (CSV)

> **Status: specified, unscheduled. Shares the importer core of FEAT-001; nothing below is implemented.
> Together, FEAT-001 + FEAT-002 constitute the full "migrate from my previous app / bank statements" path —
> supersedes the earlier statement in §3.5 of FEAT-001 that migration was not in scope.**

### 3A.1 Summary

Import **opening balances** and **historical statement transactions** for the non-investment side of the
book — bank, cash, credit-card, and loan accounts — from CSV, so a household ledger can be rebuilt from
another app or bank export history rather than entered one-by-one. Investments stay FEAT-001's job.

Two flavors:

1. **Opening balances import** — per account: balance as-of a date. Posts one double-entry transaction per
   run into the seeded **Equity ▸ Opening Balance** account ([02 §3.3](02-architecture.md)), so the ledger
   stays balanced (invariant T-1) and net worth starts correct without synthetic value games (ADR-002).
2. **Statement transactions import** — per account: rows of date, description, signed amount (or
   explicit debit/credit columns), optional category label, optional transfer flag. Importer converts each
   row to a quick-post-style transaction through the posting service; user confirms category mapping.

### 3A.2 User stories

- US-1 — As a household switching apps, I want to seed every bank/cash/credit/loan account with its opening balance so net worth + history start true.
- US-2 — As the same user, I want months of bank CSV statements imported as normal transactions I can edit/categorize later, not a frozen shadow ledger.
- US-3 — I want per-row validation with downloadable error rows, and no partial import (same safety bar as FEAT-001 US-3).
- US-4 — I want re-runs to be safe: imported rows must not silently double-post.
- US-5 — I want import provenance visible: which transactions came from which file, and the ability to back out a whole import run.

### 3A.3 Functional sketch (to promote into FR/ACs at scheduling)

| Area | Provisional behavior |
|---|---|
| Account binding | Each CSV (or column value) must map to one existing non-investment account; binding UI lists only FR-C-valid leaf accounts; credit-card statements bind to liability accounts with negation semantics handled in the row-conversion table below |
| Opening balances | One transaction per import run balancing every bound account against Equity▸Opening Balance (Q-6); leg totals must tie out to the CSV sum; refuses to run against non-empty accounts unless a deliberate safety flag is set (adds a second confirmation) |
| Row conversion | Signed-amount CSV convention: negative = debit bank/outflow →Expense; positive = deposit →Income. Explicit direction-column flavor supported. Credit-card statements: negative usually a payment (transfer) — importer detects matches to another bound account and offers to convert to a transfer (AC-T4 shape) instead of an expense, per user confirmation in preview |
| Categories | CSV category labels matched case-insensitively against existing FR-K categories; unmatched labels get **one global decision per label** in preview (create / map to existing / leave uncategorized) — never silently auto-create (Q-8) |
| Dates | ISO or locale-formatted input normalized to ISO at parse; imports follow the normal posting window unchanged (Q-7): a future-dated statement row is a row error |
| Reference & provenance | Every imported transaction stores `import_batch_id` + source row number (schema addition to `transactions`); a batch detail view lists its transactions; "reverse batch" operation is staged as `void` on all its rows (never mass-delete, per AC-T7 philosophy) |
| Dedupe | Same hash-tuple skip-and-report approach as FEAT-001 (date/account/description-normalized/amount), identical posture confirmed (Q-9) |
| Atomicity | Per-file transaction; dry-run preview with leg preview, category proposals, dedupe report, and total inflow/outflow sanity check before confirm |
| Limits & order | No date-order requirement (unlike FEAT-001 trades); same sync + size caps as FEAT-001 (5 MB / 5,000 rows, Q-4) |

### 3A.4 Architectural impact

- Extends FEAT-001's `services/importer/` with a `statements` module (row converters, category resolver,
  transfer-detector); reuses `import_mappings`, `import_batches`, wizard UI pattern.
- Posting: goes through the same `post_transaction` path as the UI (no direct line writes) — ledger
  invariants and audit behavior are exercised rather than bypassed.
- Schema: `transactions.import_batch_id FK→import_batches NULL` (indexed); adds provenance without
  touching report engines (reports blind to provenance by default; a "show import origin" column toggle
  in the transaction list is a stretch).
- Tests: L1 row-converter/category-resolver/transfer-detector units; L2 atomic import + rollback-to-void;
  L4 wizard E2E with fixture bank CSVs (including a credit-card statement with a payment match).

### 3A.5 Explicit non-goals for FEAT-002

- No PDF/OFX/QIF parsing (CSV only, same as FEAT-001).
- No auto-reconciliation against a target balance file (out of declared scope; if wanted later, its own item).
- No investment statement ingestion in FEAT-002 (FEAT-001's turf).
- No automatic expense-categorization heuristics beyond user-confirmed exact label matching.

### 3A.6 Q&A record (2026-11-08 backlog session)

| Q# | Answer | Resolved to |
|---|---|---|
| Q-6 | One tx per run | One balancing transaction per import run (every account leg vs Equity▸Opening Balance); single audit entry, one void reverses the whole run |
| Q-7 | Same posting rules | Statement rows obey the normal posting window (AC-T3/settings); a future-dated statement row is a row error, no import exemption |
| Q-8 | Global per label | One decision per unmatched label applied to all its rows (create / map to category / leave uncategorized); no per-row trivia |
| Q-9 | Skip (same as Q-1) | Hash-tuple skip + dedupe report, identical posture to FEAT-001 |
| Q-10 | Combined Import center | One wizard at `/investments/import` with tabs *Portfolio* (FEAT-001) + *Statements & Balances* (FEAT-002); shared mapping-template system (per Q-5: generic starters) |

### 3A.7 Consistency updates from the Q&A

- FEAT-001 §3.5 non-goal ("not a guaranteed migration path") is **overridden**: with FEAT-002 approved,
  the pair covers the full migration path (investments + non-investment balances/statements).
- §4 Maintenance table below is the single source of scheduling state.

## 4. Maintenance

- Opened: 2026-11-08 with FEAT-001 (user request).
- Review cadence: end of each iteration ([07 §2](07-iterative-prompts.md) R8) — promote/schedule only on the user's instruction.
- When FEAT-001 is scheduled: promote §3.3 rows into new FR-IMP-* requirements with ACs; replace this row's
  Status → included; add the roadmap row(s) in [04 §2](04-progress.md); queue a corresponding prompt template in
  [07 §6](07-iterative-prompts.md).
- Related initial-scoping note: [06 GAP G-007](06-gap-analysis.md) is superseded by FEAT-001 as the working
  record for CSV import; G-007 remains for traceability.
