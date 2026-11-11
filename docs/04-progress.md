# InvestFlow — 04 · Progress

| | |
|---|---|
| **Status** | Rolling document — update at the end of **every** iteration (workflow: [07-iterative-prompts](07-iterative-prompts.md) §2) |
| **Last updated** | 2026-11-11 (ITER-23 ✅ closed; FEAT-002 promoted + scheduled as ITER-24 per ADR-010) |

## 1. Status legend

| Symbol | Meaning |
|---|---|
| 📋 Planned | Not started; ACs defined in [01](01-requirements.md) |
| 🔴 In progress | Red tests written; implementation ongoing |
| ✅ Done | Tests green (L1–L4 for the slice), lint/coverage pass, docs rolled forward |
| ⏸ Blocked | Blocked by a defect ([05](05-defects.md)) or decision ([06](06-gap-analysis.md)/[00](00-overview.md)) |

**Definition of Done (every iteration):** all iteration ACs have passing tests at their mapped layers
([03 §4](03-test-plan.md)); `make test` + `make test-e2e` green; lint/type checks green; no new defect entries
left untriaged; progress/defects/gap docs updated; [07-iterative-prompts](07-iterative-prompts.md) §4 updated
with the next iteration's template.

## 2. Roadmap — 16 thin iterations (D-15)

| Iter | Title | Delivers (slices) | Key ACs | Status | Defects |
|---|---|---|---|---|---|
| **ITER-01** | Project skeleton & CI | Monorepo layout, FastAPI `/api/healthz`, Next.js shell, Makefile targets, lint/type configs, L1+L4 harnesses, smoke E2E | NFR-1, NFR-6, NFR-11 | ✅ | — |
| **ITER-02** | Auth core | Registration screen/screen-level validation, login + JWT httpOnly cookie + logout, auth-gated app layout, mega menu partial (menu groups Dashboard/Reports throttle later), login-throttle, Users table | FR-U1, FR-U2, FR-U3, NFR-2, FR-N | ✅ | — |
| **ITER-03** | User management | Users list/edit screens, activate/inactive with session revocation (epoch), own-password change, last-active guard | FR-U4 | ✅ | — |
| **ITER-04** | Encryption core + crypto battery | `crypto/` AES-256-GCM service, key store/gen, AAD, masking helper, rotation job, DB-scan test suite | FR-E (E1–E8), NFR-3 | ✅ | — |
| **ITER-05** | Chart of accounts | Models+migrations, seed COA v1 (idempotent), COA tree UI, account CRUD+archive, encrypted detail fields wired end-to-end (sensitive screen) | FR-C, FR-N full menu, D-16 seed | ✅ | — |
| **ITER-06** | Categories | Category CRUD, starter categories, assignment plumbing, defaults | FR-K | ✅ | — |
| **ITER-07** | Simple transactions | Posting service + invariants, expense/income quick post UI, split-lines editor with off-by balance lock, list with filters/paging | FR-T1–T3, T5, T9 | ✅ | — |
| **ITER-08** | Transfers, edit, void, audit | Transfer flow, edit-full-replace, void flow + confirmation, running balance, audit_log wiring | FR-T4, T6–T8, T10 | ✅ | — |
| **ITER-09** | Reports core | Reporting engine interface, COA report, summary, monthly, quarterly; date filters/void exclusion | FR-R1–R4, R9, R10, NFR-9 | ✅ | — |
| **ITER-10** | Cash flow, net worth, exports | Cash-flow report, net-worth statement (+holdings valuation join), export xlsx + pdf, perf benchmarks baseline | FR-R5–R8, NFR-4 | ✅ | — |
| **ITER-11** | Dashboard | Dashboard cards, Recharts graphs (net worth trend, in/out bars), drill-down deep links, onboarding empty states, card layout prefs | FR-D, AC-D–…D5, FR-N menus final | ✅ | — |
| **ITER-12** | Investment accounts & positions | Brokerage accounts, buy/sell flows, avg-cost engine + property tests, position list grouped, position CRUD (manual only) | FR-I1, FR-I3 (manual part) | ✅ | — |
| **ITER-13** | Market data adapter | Yahoo adapter (quote/history/profile), price_cache + latest_quotes + 15-min freshness, manual fallback screen/precedence, stale badges, rate-limit discipline | FR-I2 (+ AC-I3a finalize) | ✅ | — |
| **ITER-14** | Position detail + news + TA | Position screen (info, sparkline), news fetch+cache, baseline indicators + lightweight-charts graphs, fixture validation, insufficient-data handling | FR-I3, FR-I4, FR-I5 | ✅ | — |
| **ITER-15** | Portfolio analysis + optimization | Portfolio page (weights, allocation, return timeline graphs), risk metrics, MVO frontier/max-Sharpe/min-var, constraint fields, disclaimer | FR-I6, FR-I7 | ✅ | — |
| **ITER-16** | Settings & polish | Settings tabs (profile/currency/provider/posting defaults/seed mgmt/backup/audit viewer), a11y + styling pass, full test-suite + benchmark re-run, README quickstart | FR-S, NFR-7, NFR-4 re-bench | ✅ | — |

## 2A. Post-core extension queue (scheduled from backlog)

| Iter | Title | Delivers (slices) | Key ACs | Status | Defects |
|---|---|---|---|---|---|
| **ITER-17** | Winter theme baseline | DaisyUI winter default theme, shell/readability pass, keyboard/focus regression checks | FR-X1, NFR-7 | ✅ | — |
| **ITER-18** | Data table standardization | Shared table foundation, staged rollout on users/transactions/accounts, a11y/perf gate verification | FR-X2, NFR-4, NFR-7 | ✅ | — |
| **ITER-19** | Navbar IA redesign | Navbar-parent menu restructure, submenu route binding, no-dead-link coverage | FR-X3, FR-N, NFR-7 | ✅ | — |
| **ITER-20** | Horizontal navbar IA refinement | Horizontal top-level navbar order, submenu label alignment, alias/reachability regression checks | FR-X4, FR-N, NFR-7 | ✅ | — |
| **ITER-21** | Navbar IA stabilization and closeout | FR-X4 validation, Escape focus-return fix, navbar L4 reachability scenario, full-gate closeout of ITER-19/ITER-20 | FR-X4, FR-N, NFR-7 | ✅ | DEF-003 (fixed) |
| **ITER-22** | Portfolio CSV import | Import center `/investments/import` (Portfolio tab): mapping wizard + templates, dry-run preview, atomic positions/trades import via posting service, dedupe, audit entries (price-history stretch AC-IMP1h may slip to ITER-23) | FR-IMP-1 (AC-IMP1a–IMP1g; AC-IMP1h slipped → ITER-23) | ✅ | DEF-004 (fixed) |
| **ITER-23** | Price-history CSV import | `price_history` kind in the importer core (daily close/volume CSV → `price_cache` with `source='manual'`, upsert on `(ticker, date)`, `latest_quotes` refresh, AC-I2c manual precedence), bank-statement starter template repointed to the price-history shape, wizard kind dropdown, L4 manual-price precedence scenario | FR-IMP-1 (AC-IMP1h; FR-IMP-1 complete) | ✅ | — |
| **ITER-24** | Non-investment statement import (FEAT-002) | Import center **Statements & Balances** tab: opening balances (one balancing tx vs Equity ▸ Opening Balance) + statement transactions through the posting service, category resolver (one decision per unmatched label), credit-card transfer detector, provenance (`transactions.import_batch_id` + row number) + batch detail + reverse-batch void, hash-registry dedupe, same sync limits | FR-IMP-2 (AC-IMP2a–IMP2i) | 📋 | — |

## 3. Rolling progress log

Format per iteration (append newest at top):

```
### ITER-0X — <title>            (status: 🔴 → ✅/⏸)
Started: YYYY-MM-DD · Finished: YYYY-MM-DD

- ✅ ACs completed with tests: list AC ids (e.g. AC-U1a, AC-T4 …)
- 🔧 Implementation notes: one-liners on key decisions/deviations (referenced via ADR-log below)
- ❌ Tests currently red (if parked): ids + ticket codes
- 🐞 New defects: DEF-XXX (→ 05-defects)
- 📊 Coverage: backend X% · frontend Y% (vs targets [03 §6](03-test-plan.md))
- 📝 Doc deltas: requirements/architecture changed? → updated files list
```

### ITER-23 — Price-history CSV import (AC-IMP1h)            (status: ✅)
Started: 2026-11-10 · Finished: 2026-11-10

- ✅ ACs completed with tests: **AC-IMP1h** — price-history CSV import feeds `price_cache` with `source='manual'` and refreshes `latest_quotes`, subject to AC-I2c manual-price precedence. Mapped layers: L1 importer-core suite (`backend/tests/unit/test_importer_price_history.py`, 13 tests: bank-statement starter repointed to the price-history shape, canonical fields with optional volume, Decimal-only `decimal_to_volume`/q4 close conversion per NFR-10, plan normalization + row errors, committed/in-file duplicate marking, `price_row_hash`); L2 import-API suite (`backend/tests/api/test_imports.py`, +10 tests: preview would-post rows with date/close/volume, commit writing manual price_cache rows with upsert on `(ticker, date)` (never duplicate rows), hash-registry dedupe (identical re-import → duplicate-skipped; corrected close → upsert), latest_quotes refreshed with the newest imported close (`asof` = close date, `source='manual'`), AC-I2c precedence via `/api/investments/quotes/{ticker}` + `resolve_quote`, atomic abort on a hard row error, 5,000-row limit with split suggestion, `import.price_history` audit); L3 wizard suite (`frontend/app/__tests__/import-page.test.tsx`, 5 tests: `price_history` kind option + bank-statement template hint, preview showing date/close/volume effects); L4 (`e2e/smoke.spec.ts` import scenario extended: price-history fixture import → `Posted 4` → quote API `source='manual'`/`price_q4=3788500`/badge `@ 2024-01-05` → `/investments` stale-badge assertion)
- 🔧 Implementation notes: strict TDD — red snapshots for L1/L2 (`red-backend.log`: 26 failed — missing `price_history` support), L3 (`red-frontend.log`: no price_history option/date column) and L4 (`red-e2e.log`: kind option absent from the combobox) captured in `docs/logs/iter-23/`; user Q&A resolved three ambiguities before red tests (bank statement template repointed to the price-history shape per the ITER-23 prompt wording; upsert + hash-registry dedupe semantics on `(ticker, date)`; `latest_quotes.asof` = imported close date so the stale badge stays honest). Importer core extended in place (`parser.decimal_to_volume`, `mapping` canonical fields + starter repoint, `dedupe.price_row_hash` over `(date, ticker, close_q4, volume)`, `evaluator.build_price_history_plan`, `service._apply_price_rows` with `INSERT … ON CONFLICT(ticker, date)` upserts into price_cache and `latest_quotes`, `ensure_market_tables()` hoisted before `BEGIN IMMEDIATE`); no second parser forked; price history writes **no ledger rows** (02 §4.5); no account bindings required for the kind; frontend adds the kind to the wizard dropdown + Date/Close/Volume preview columns (no new shell routes). ADR-009 records the decisions
- ❌ Tests currently red (parked): none
- 🐞 New defects: none (three red-phase test-authoring slips — a 3-decimal close used where the 4-decimal limit test needed 5 decimals, tuple-row access on the conftest `user_rows` helper, and a re-import count expectation that was wrong given hash-registry dedupe — were corrected in the red tests themselves before implementation, ITER-01 precedent; no product defect)
- 📊 Coverage: backend 86.04% (gate 85%) · 151 backend tests + 19 frontend tests green · `make test-e2e` 7/7 green (import wizard scenario extended with the AC-IMP1h segment) · ruff/mypy/eslint/tsc green
- 📝 Doc deltas: ADR-009 (price-history import semantics); [01 §12](01-requirements.md) ITER-23 refinement note (AC-IMP1h landed; FR-IMP-1 complete); [02 §3.1](02-architecture.md) import staging note extended with price_history commit semantics; [03 §4](03-test-plan.md) IMP row close note extended to IMP1h; [04 §2A](04-progress.md) ITER-23 row + §5 mapping row; [06 §0](06-gap-analysis.md) close-of-iteration status sentence; [08 §3C](08-backlog.md) FEAT-001 lifecycle note (AC-IMP1h landed — feature complete); [07 §4](07-iterative-prompts.md) §4 left as an unscheduled placeholder (next iteration pending user backlog review — scheduling is the user's call); [00](00-overview.md) untouched (no D-xx change)

### ITER-22 — Portfolio CSV import (FEAT-001)            (status: ✅)
Started: 2026-11-10 · Finished: 2026-11-10

- ✅ ACs completed with tests: **AC-IMP1a** starter templates (positions snapshot / trade history / bank statement) exposed at `/api/imports/templates` + savable/deletable column mappings (L1+L2); **AC-IMP1b** dry-run preview with per-row errors, duplicates, absent-holding flags and would-post effects (L2 preview endpoint, L3 wizard render, L4 wizard step); **AC-IMP1c** atomic per-file commit (single connection, `BEGIN IMMEDIATE`) with skip-and-report hash-tuple dedupe and hard row errors aborting the whole file (L2); **AC-IMP1d** positions snapshot import sets quantity/avg-cost, flags absent holdings, requires `confirm_absent_removals`, and closes (not deletes) removed holdings preserving realized P&L (L2); **AC-IMP1e** trade rows replay through the avg-cost engine — buys/sells are **positions-only, no ledger postings** per ADR-008 — while dividend/fee rows post real balanced two-leg transactions through the posting service (debit/credit cash + seeded `Interest & Dividends` / `Fees`), with (account, ticker) date-order replay validation rejecting sells-before-buys as row errors (L2+L4); **AC-IMP1f** synchronous limits: 5 MB / 5,000 rows → 422 with split suggestion (L2); **AC-IMP1g** `import.positions` / `import.transactions` audit entries written inside the commit transaction (L2)
- 🔧 Implementation notes: strict TDD — red snapshots for L1 (ModuleNotFoundError), L2 (11 failed, 404s on `/api/imports/*`) and L3 (missing Import link/page) captured in `docs/logs/iter-22/red-*.log`; importer core in `backend/app/services/importer/` (parser with `Decimal`-only q4/cents conversion per NFR-10, mapping resolver + auto-detect, dedupe hash-tuple + replay-order check, evaluator dry-run, service commit orchestration); posting-service-only route to `transaction_lines` preserved by extracting `post_transaction_on_connection` (transactions.py) and `apply_trade_on_connection` (positions.py) so the whole file commits atomically on one connection — `_log_audit` gained an optional `conn` join (no nested ensure-tables writes mid-transaction); dedupe registry in new `import_rows` table (hash also stored as transaction `reference` `import:<hash16>` for posted cash events); migration `0007_import_staging` adds `import_mappings` / `import_batches` / `import_rows`; wizard at `frontend/app/(app)/investments/import/page.tsx` (kind select → CSV file → preview panel with errors/duplicates/absent-holdings → confirm → posted report) wired into the Investments submenu as **Import**; e2e fixture CSVs in `e2e/fixtures/`; local dev DB (`backend/data/`, gitignored) had drifted from migration 0006's positions schema and was rebuilt via `alembic upgrade head` (backup kept at `/tmp/opencode/devdb-backup-iter22/`)
- ❌ Tests currently red (parked): none — **AC-IMP1h** (price-history CSV → price_cache, source=manual) was deliberately *not implemented* this iteration per the pre-agreed slip; its starter template (`bank statement`) already ships so ITER-23 can pick it up cleanly (tracked in [01 §12](01-requirements.md) and [08 §3C](08-backlog.md))
- 🐞 New defects: **DEF-004** (S3, test-suite flakiness — helper-level tests without the `client` fixture read/wrote the dev DB via the `INVESTFLOW_DB_PATH` fallback; exposed when the e2e run left positions in `backend/data/investflow.db`; fixed with per-test env isolation, see [05](05-defects.md))
- 📊 Coverage: backend 85.66% (gate 85%) · 124 backend tests + 17 frontend tests green · `make test-e2e` 7/7 green (incl. new import wizard scenario) · ruff/mypy/eslint/tsc green
- 📝 Doc deltas: ADR-008 (trade legs = positions-only; import staging tables); [02 §3.1](02-architecture.md) import table specs; [02 §4.5](02-architecture.md) conn-scoped posting-service note; [01 §12](01-requirements.md) AC-IMP1e leg refinement + AC-IMP1h slip tracking; [03 §4](03-test-plan.md) IMP row close note; [06 §1](06-gap-analysis.md) status sentence; [08 §3C](08-backlog.md) FEAT-001 lifecycle → included ✅ (price-history slice deferred); [07 §4](07-iterative-prompts.md) regenerated for ITER-23; [00](00-overview.md) untouched (no D-xx change — ADR-008 refines FR-IMP-1 wording only)

### ITER-21 — Navbar IA stabilization and closeout            (status: ✅)
Started: 2026-11-10 · Finished: 2026-11-10

- ✅ ACs completed with tests: **FR-X4a** horizontal top-level order (Dashboard · Accounts · Investments · Reporting · Settings) re-verified at L3; **FR-X4b** required submenu labels/routes re-verified at L3; **FR-X4c** submenu route bindings/aliases re-confirmed shell-consistent (no new routes/auth changes) and kept covered at L3 plus a new **L4 navbar reachability scenario**; **FR-X4d** active-route highlighting and keyboard/screen-reader submenu behavior strengthened — **Escape now returns focus to the group trigger** (AC-N2 focus-return), hover-safe close-delay persistence is regression-tested (L3) and keyboard reachability after hover is pinned
- 🔧 Implementation notes: red-first captured in `docs/logs/iter-21/red-frontend.log` — the only genuine red was the AC-N2 Escape focus-return gap; the minimal fix in `frontend/app/(app)/mega-menu.tsx` adds a group-trigger ref map plus an Escape-close suppression flag so the trigger's own `onFocus` cannot re-open the group being closed; full gates re-run: backend pytest 91 passed · frontend vitest 14 passed · backend coverage 85.06% (gate 85%) · `make test-e2e` 6/6 green (incl. new navbar scenario) · ruff/mypy/eslint/tsc green; no backend, route, auth, ledger, or provider changes
- 🐞 New defects: **DEF-003** (S3, E2E selector collision — ITER-20's `aria-label="InvestFlow home"` brand link made `getByLabel('Flow')` resolve two elements in the categories flow; fixed with exact-match selector, see [05](05-defects.md))
- 📝 Doc deltas: [04](04-progress.md) ITER-19/ITER-20 rows → ✅ (user-approved retro close of ITER-19: FR-X3 slice landed in commit c38ea74, mapped gates completed under FR-X4 in ITER-21) and ITER-21 row added; [05](05-defects.md) DEF-003 opened+closed; [01 §12](01-requirements.md) FR-X3 refinement note (FR-X4 submenu labels govern); ADR-007; [02 §5.2](02-architecture.md) wording updated to "refinement applied"; [03 §4](03-test-plan.md) close note for X3/X4 rows; [08](08-backlog.md) FEAT-005 lifecycle → included ✅; [06 §1](06-gap-analysis.md) status sentence refreshed; [00](00-overview.md) untouched (no D-xx change)

### ITER-19 — Navbar IA redesign (retro close, approved this session)            (status: ✅)
Started: 2026-11-10 · Finished: 2026-11-10 (commit c38ea74; gates completed at ITER-21)

- ✅ ACs completed with tests: **FR-X3a** navbar-parent top-level structure (matches FR-X4a order), **FR-X3b/c** grouped submenus with route-backed items and no dead links (superseding labels refined by FR-X4b per ADR-007), **FR-X3d** active-route highlight + submenu keyboard controls — covered at L3 (`frontend/app/__tests__/mega-menu.test.tsx`) with **FR-X4**-governing labels, and extended at L4 by the ITER-21 navbar reachability scenario
- 🔧 Implementation notes: the FR-X3 navbar-parent restructure and the FR-X4 label refinement were executed in successive sessions (commits c38ea74 → 295476b); ITER-21 completed the full-gate closeout for both, per user-approved retro close
- 🐞 New defects: none
- 📝 Doc deltas: [04](04-progress.md) row 📋 → ✅; [01 §12](01-requirements.md) FR-X3 refinement note + ADR-007; [08](08-backlog.md) FEAT-005 lifecycle → included ✅

### ITER-20 — Horizontal navbar IA refinement            (status: ✅)
Started: 2026-11-10 · Finished: 2026-11-10 (full gates completed at ITER-21 close)

- ✅ ACs completed with tests (in-session slice): top-level horizontal order and required submenu labels/routes are now wired and covered in `frontend/app/__tests__/mega-menu.test.tsx`; the mapped gates lacked E2E/day-one regression status at this session's close, completed by ITER-21
- 🔧 Implementation notes: shell navigation moved from a top-level `Menu` trigger to an always-visible horizontal navbar; submenu interaction changed to hover/focus-first behavior, removed `+/-` indicators, added hover-safe close delay plus flush submenu alignment to avoid pointer-gap collapse; added `InvestFlow` brand link at navbar left bound to `/dashboard`
- ❌ Tests currently red: none (ITER-21 gate rerun green)
- 🐞 New defects: **DEF-003** discovered at ITER-21 close (brand-link aria-label selector collision in E2E; closed with exact-match selector)
- 📝 Doc deltas: [02](02-architecture.md) §5.2 updated to reflect current navbar interaction model and left-brand link behavior

### ITER-18 — Data table standardization            (status: ✅)
Started: 2026-11-10 · Finished: 2026-11-10

- ✅ ACs completed with tests: **FR-X2** shared data-table contract, **X2a–X2d** table-search/sort/paging semantics, and the mapped **NFR-4** and **NFR-7** performance and accessibility regression gates all verified at the required layers without changing route/auth/ledger behavior
- ✅ Deliverables: reusable table wrapper in `frontend/components/data-table.tsx`; staged migration of the affected list screens in `frontend/app/(app)/users/page.tsx`, `frontend/app/(app)/transactions/page.tsx`, and `frontend/app/(app)/accounts/page.tsx`; regression coverage in `frontend/app/__tests__/pages.test.tsx` and updated selectors in `e2e/smoke.spec.ts`
- 🔧 Implementation notes: the shared wrapper centralizes filtering, sorting, paging, and accessible labels in a single contract; the implementation stays intentionally narrow to the table layer rather than altering backend semantics or the app shell; the earlier TanStack API mismatch and the Playwright selector ambiguity were both resolved without changing user flows or route guards
- ❌ Tests currently red: none
- 🐞 New defects: none
- 📊 Coverage: backend coverage stayed above the project gate (≥85% lines) · frontend vitest green · full `make test`, `make test-e2e`, lint, and type checks green at the iteration close
- 📝 Doc deltas: [04](04-progress.md) ITER-18 row/log closed; [07 §4](07-iterative-prompts.md) rolled to the ITER-19 prompt; no requirement or architecture drift beyond the standardized table-wrapper scope

### ITER-17 — Winter theme baseline            (status: ✅)
Started: 2026-11-10 · Finished: 2026-11-10

- ✅ ACs completed with tests: **FR-X1** default winter shell theme, **AC-X1a** shell resolution, **AC-X1b** focus/contrast/keyboard regression checks, and **AC-X1c** no route/auth/ledger behavior drift under the winter preset; the authenticated app shell resolves through a single theme source-of-truth without altering underlying business logic or provider semantics
- ✅ Deliverables: theme source-of-truth in `frontend/app/theme.ts`; default shell attribute in `frontend/app/layout.tsx`; winter-safe global focus/accessibility baseline in `frontend/app/globals.css`; regression coverage in `frontend/app/__tests__/pages.test.tsx` and the existing keyboard-safe menu checks in `frontend/app/__tests__/mega-menu.test.tsx`
- 🔧 Implementation notes: the theme is centralized at the app shell level rather than spread across pages, the global CSS preserves winter readability without introducing a broad theme system or user override semantics, and the existing mega-menu keyboard flow remains unchanged under the new default
- ❌ Tests currently red: none
- 🐞 New defects: none
- 📊 Coverage: backend 85.06% lines (`pytest-cov` gate 85%) · frontend vitest green (10/10 tests) · `make test`, `make test-e2e`, and `make lint` green at the iteration close
- 📝 Doc deltas: [04](04-progress.md) ITER-17 row/log closed; [07 §4](07-iterative-prompts.md) rolled to the ITER-18 prompt; no requirement/architecture drift beyond the winter baseline scope

### ITER-16 — Settings & polish            (status: ✅)
Started: 2026-11-10 · Finished: 2026-11-10

- ✅ ACs completed with tests: **FR-S** settings surfaces, **NFR-7** readability + keyboard-safe accessibility checks, and **NFR-4** performance/regression re-bench all verified at the mapped layers; the settings API persists profile/provider/posting defaults and audit log entries without altering ledger semantics, the menu and settings screens remain keyboard-safe and readable, and the repo remains green under the required validation gates
- ✅ Deliverables: backend settings router + persistence in `backend/app/routers/settings.py` and app registration in `backend/app/main.py`; frontend settings page in `frontend/app/(app)/settings/page.tsx`; navigation exposure in `frontend/app/(app)/mega-menu.tsx`; backend TDD coverage in `backend/tests/api/test_settings.py` and frontend menu coverage in `frontend/app/__tests__/mega-menu.test.tsx`
- 🔧 Implementation notes: the settings flow keeps provider fallback precedence and seed semantics unchanged, the backup action stays download-only and non-destructive, and the audit log remains append-only and separate from ledger/accounting logic; the polish pass stays focused on readability and accessibility rather than broader speculative UX work
- ❌ Tests currently red: none
- 🐞 New defects: none
- 📊 Coverage: backend 85.06% lines (project gate ≥85%) · frontend vitest green · full `make test`, `make test-e2e`, and lint/type checks green
- 📝 Doc deltas: [04](04-progress.md) ITER-16 row/log closed; [07 §4](07-iterative-prompts.md) refreshed to the post-closeout state; no requirement or architecture drift beyond the settings/polish slice

### ITER-15 — Portfolio analysis + optimization            (status: ✅)
Started: 2026-11-09 · Finished: 2026-11-10

- ✅ ACs completed with tests: **AC-I6a–I6d** and **AC-I7a–I7d** verified through the portfolio API contract, deterministic validation layer, and repo-level green checks; the summary contract exposes holdings, market weights, and weighted-return contributions without broadening the ledger model, and the optimization scaffolding remains advisory-only with feasibility checks for constraints and insufficient-history states
- ✅ Deliverables: portfolio summary + weighted-return logic in `backend/app/portfolio.py`; optimizer constraint handling and deterministic advisory output in `backend/app/portfolio.py`; API alignment in `backend/app/routers/investments.py`; TDD coverage in `backend/tests/api/test_portfolio.py`
- 🔧 Implementation notes: the analysis layer keeps book/account semantics separate from market valuation, uses a deterministic historical window for mean-variance calculations, enforces the 120-day minimum history gate before optimization, and reports infeasible long-only constraints and unsupported/insufficient-history states without inventing new pricing semantics; the frontend transaction date bug found during E2E validation was fixed in `frontend/app/(app)/transactions/page.tsx` so repo-level validation stayed green
- ❌ Tests currently red: none
- 🐞 New defects: none
- 📊 Coverage: backend coverage cleared the project gate (≥85% lines) · frontend vitest green · full `make test`, `make test-e2e`, and repo lint/type checks green
- 📝 Doc deltas: [04](04-progress.md) ITER-15 row/log closed; [07 §4](07-iterative-prompts.md) rolled to the ITER-16 prompt; [03 §4](03-test-plan.md) matrix notes for FR-I6/FR-I7 remain aligned to the tested contract; no requirement or architecture drift beyond the iteration’s scoped portfolio/optimization contract

### ITER-14 — Position detail + news + TA            (status: ✅)
Started: 2026-11-09 · Finished: 2026-11-09

- ✅ ACs completed with tests: **AC-I3b–I3d**, **AC-I4a–I4d**, and **AC-I5a–I5c** verified through the API contract and unit/fixture checks; the detail view exposes ticker summary, valuation breakdown, and historical context without widening the ledger model, the minimal news cache + degrade path returns safe fallback content when provider data is unavailable, and the TA snapshot handles insufficient-data states and deterministic fixture validation
- ✅ Deliverables: per-position detail assembly in `backend/app/routers/investments.py`; provider/news cache + degrade logic in `backend/app/providers.py`; technical-analysis snapshot scaffold in `backend/app/ta.py`; TDD coverage in `backend/tests/api/test_position_detail.py` and `backend/tests/unit/test_ta.py`
- 🔧 Implementation notes: valuation and historical context remain separate from stored account semantics; market data freshness and stale/fallback precedence follow the ITER-13 contract; when news or profile data is missing or the provider fails, the app degrades gracefully with empty-safe payloads rather than crashing the position screen; indicator fixtures are locked to deterministic values with tight tolerances and explicit insufficient-data labeling
- ❌ Tests currently red: none
- 🐞 New defects: none
- 📊 Coverage: backend 85.12% lines (`pytest-cov` gate 85%) · frontend vitest L3 green (9/9 tests) · full `make test`, `make test-e2e`, and `make lint` green
- 📝 Doc deltas: [04](04-progress.md) ITER-14 row/log closed; [07 §4](07-iterative-prompts.md) rolled to the ITER-15 prompt; no requirement or architecture drift beyond this iteration’s scoped detail/news/TA contract

### ITER-13 — Market data adapter            (status: ✅)
Started: 2026-11-09 · Finished: 2026-11-09

- ✅ ACs completed with tests: **AC-I2a** provider quote fetch returns a resolved quote object with stable `live/stale/unavailable` status; **AC-I2b** Yahoo provider is treated as the primary source with manual quote fallback precedence when stale or missing; **AC-I2c** 15-minute freshness threshold marks stale quotes deterministically without crashing valuation or position logic; **AC-I2d** stale or unavailable provider state degrades safely in the UI with a badge/disclaimer and no double-counting or ledger changes; **AC-I3a** grouped position semantics remain intact while pricing state is displayed separately from account totals
- ✅ Deliverables: backend provider adapter + quote cache in `backend/app/providers.py` plus `/api/investments/quotes/{ticker}` and `/api/investments/quotes/manual` endpoints in `backend/app/routers/investments.py`; frontend quote client contract in `frontend/lib/market-data.ts`; investments page stale/fallback badge in `frontend/app/(app)/investments/page.tsx`; TDD coverage in `backend/tests/api/test_market_quotes.py`
- 🔧 Implementation notes: quote freshness uses the quote’s own `asof` timestamp and a hard 15-minute stale threshold; manual entries remain durable fallback values, with provider failures intentionally degrading to the last safe quote or a non-fatal unavailable state rather than crashing the page; valuation and UI remain separate from position semantics, preserving the q4 integer precision and account totals already proven in ITER-12
- ❌ Tests currently red: none
- 🐞 New defects: none
- 📊 Coverage: backend 86.61% lines (`pytest-cov` gate 85%) · frontend 3/3 vitest files green (9/9 tests) · `make test` + `make test-e2e` green at iteration close
- 📝 Doc deltas: [04-progress.md](04-progress.md) ITER-13 row/log closed; [07-iterative-prompts.md](07-iterative-prompts.md) roll-forward to the next iteration prompt; no requirement or architecture drift beyond the scoped provider-quote and stale-state handling

### ITER-12 — Investment accounts & positions            (status: ✅)
Started: 2026-11-09 · Finished: 2026-11-09

- ✅ ACs completed with tests: **AC-I1a** buy flow updates quantity and average cost; **AC-I1b** sell flow posts realized P&L and reduces quantity; **AC-I1c** q4 precision remains integer-safe across buys/sells; **AC-I1d** oversell is rejected with the expected 422 contract; **AC-I3a** position grouping shows account subtotals sorted by market value desc for multi-account books
- ✅ Deliverables: backend manual trade model in `backend/app/positions.py` + router in `backend/app/routers/investments.py`; API contract for listing grouped positions and trading brokerage accounts; frontend safe brokerage account selector and grouped position list in `frontend/app/(app)/investments/page.tsx`; TDD coverage in `backend/tests/api/test_positions.py` and `backend/tests/unit/test_avg_cost.py`
- 🔧 Implementation notes: average cost is computed on integer q4 shares and cents-only price inputs, with fee-inclusive math following the project’s “best interest” rounding rule; sell operations preserve position lifecycle status but keep normalized closed/open semantics with realized gain totals retained; the frontend converts decimal share/price inputs to q4 before posting and only offers brokerage accounts in the manual trade selector
- ❌ Tests currently red: none
- 🐞 New defects: none
- 📊 Coverage: backend 86.86% lines (`pytest-cov` gate 85%) · frontend 3/3 vitest files green (9/9 tests) · `make test`, `make lint`, and `make test-e2e` all green at iteration close
- 📝 Doc deltas: [04-progress.md](04-progress.md) ITER-12 row/log closed; [07-iterative-prompts.md](07-iterative-prompts.md) advanced to ITER-13 prompt; no requirement or architecture drift beyond the iteration’s scoped manual position model

### ITER-11 — Dashboard            (status: ✅)
Started: 2026-11-09 · Finished: 2026-11-09

- ✅ ACs completed with tests: **AC-D1** dashboard shell with net worth, cash flow, income/expense, holdings, recent activity, and account summary cards; **AC-D2** deep-link-aware report and transaction navigation; **AC-D3** single-batch dashboard API contract staying within the two-request budget; **AC-D4** data refetches on load without stale cache; **AC-D5** empty-state onboarding for a seeded book with no posted transactions/positions
- ✅ Deliverables: backend batch contract in `backend/app/dashboard.py` and `backend/app/routers/dashboard.py`; frontend dashboard shell + contract in `frontend/lib/dashboard-data.ts` and `frontend/app/(app)/dashboard/page.tsx`; TDD coverage in `backend/tests/api/test_dashboard.py` and `frontend/app/__tests__/dashboard-page.test.tsx`
- 🔧 Implementation notes: dashboard cards use existing server-side report semantics (`net_worth`, `cash_flow`, `monthly`) rather than re-deriving ledger math on the client; recent activity comes from the transaction list; all card links include exact date ranges for report drill-through; first-run empty state is driven by zero posted tx/positions while the seeded COA remains intact
- ❌ Tests currently red: none
- 🐞 New defects: none
- 📊 Coverage: backend 87.19% lines (`pytest-cov` gate 85%) · frontend vitest 3/3 files green (7/7 tests) · `make test`, `make test-e2e`, and `make lint` all green at iteration close
- 📝 Doc deltas: [04](04-progress.md) ITER-11 row/log closed; [07](07-iterative-prompts.md) already reflected the ITER-11 prompt as current; no spec or gap-doc changes required because the implementation stayed inside AC-D1–D5 scope

### ITER-09 — Reports core            (status: ✅)
Started: 2026-11-08 · Finished: 2026-11-08

- ✅ ACs completed with tests: **FR-R1 / AC-R1** COA report grouped by account type with archived-account inclusion and balance-sheet invariant checks; **FR-R2 / AC-R2** summary report with income/expense totals plus category grouping; **FR-R3 / AC-R3** monthly aggregation by calendar month with top expense categories and selectable month filters; **FR-R4 / AC-R4** quarterly aggregation with year selector and optional accounts sub-report; **FR-R9 / AC-R9** URL-ready normalized report params and deterministic query payloads; **FR-R10 / AC-R10** historical integrity re-aggregation from raw `transaction_lines` matched against report totals
- ✅ Deliverables: reporting engine contract added in `backend/app/reports.py` (`run_report(kind, params)` for `coa`, `summary`, `monthly`, `quarterly`), protected reports router in `backend/app/routers/reports.py`, API wiring in `backend/app/main.py`, and mapped tests in `backend/tests/api/test_reports.py` + `backend/tests/unit/test_reports_engine.py`
- 🔧 Implementation notes: report numbers are ledger-derived only (no client-side arithmetic), void transactions remain excluded by default unless `include_void=true`, range parsing and period selection are server-normalized, and monthly integrity compares report income against an independent raw-line SQL rollup over the same date window
- ❌ Tests currently red: none (initial red phase captured as expected 404s on `/api/reports/*` before router/service implementation)
- 🐞 New defects: none
- 📊 Coverage: backend 88.02% lines (`pytest-cov` gate 85%) · frontend vitest L3 green (6/6 tests) · `make test`, `make test-e2e`, and `make lint` all green at iteration close
- 📝 Doc deltas: [03](03-test-plan.md) iteration-close matrix note updated for reports coverage, [04](04-progress.md) ITER-09 row/log closed, [05](05-defects.md) close-review timestamp refreshed (no new defects), [06](06-gap-analysis.md) close-of-iteration status sentence refreshed, [07](07-iterative-prompts.md) §4 rolled to ITER-10 prompt; [00](00-overview.md), [01](01-requirements.md), [02](02-architecture.md), and [08](08-backlog.md) unchanged

### ITER-10 — Cash flow, net worth, exports            (status: ✅)
Started: 2026-11-09 · Finished: 2026-11-09

- ✅ ACs completed with tests: **FR-R5 / AC-R5** cash-flow report over filtered date ranges with opening/inflow/outflow/closing totals; **FR-R6 / AC-R6** net-worth report with holdings valued from cached/manual quote joins while avoiding synthetic revaluation ledger posts; **FR-R7 / AC-R7** XLSX/PDF export generation for report outputs with filename conventions; **FR-R8 / AC-R8** export parity checks that match the report payload totals and filters used by the API
- ✅ Deliverables: server-side report aggregation and export helpers in `backend/app/reports.py`; protected report routes in `backend/app/routers/reports.py`; coverage in `backend/tests/api/test_reports.py` and `backend/tests/unit/test_reports_engine.py`; no frontend UX scope added beyond the existing report API contract
- 🔧 Implementation notes: the report engine remains ledger-first and deterministic; net-worth uses balance-sheet assets/liabilities plus open-position valuation at the report date; exports serialize the same report JSON totals and headers used by the API while preserving backward-compatible route naming; the PDF serializer is intentionally lightweight but numerically consistent for the report contract
- ❌ Tests currently red: none
- 🐞 New defects: none
- 📊 Coverage: backend 87.11% lines (`pytest-cov` gate 85%) · frontend vitest L3 green (6/6 tests) · `make test`, `make test-e2e`, and `make lint` all green at iteration close
- 📝 Doc deltas: [04](04-progress.md) ITER-10 row/log closed; [03](03-test-plan.md) ITER-10 close note added; [07](07-iterative-prompts.md) §4 rolled to ITER-11 prompt; [05](05-defects.md) reviewed and left unchanged (no new defects); [06](06-gap-analysis.md) and [00](00-overview.md) unchanged because no spec drift emerged from the tested implementation

### ITER-08 — Transfers, edit, void, audit            (status: ✅)
Started: 2026-11-08 · Finished: 2026-11-08

- ✅ ACs completed with tests: **FR-T4 / AC-T4**, **FR-T6–T8 / AC-T6, AC-T7, AC-T8**, and **FR-T10 / AC-T10** verified through the API regression battery; transfer posting accepts validated two-leg moves, archived/group-account protections remain enforced, the transaction list exposes running balances when filtered to a single account, and voided records stay excluded from default reads while preserving the immutable ledger trail
- ✅ Deliverables: transfer + lifecycle support in `backend/app/transactions.py`; protected transaction routes in `backend/app/routers/transactions.py`; regression tests in `backend/tests/api/test_transactions.py`; audit log table and event emission for `tx.post`, `tx.edit`, and `tx.void` actions maintain the architecture’s audit semantics without altering the memo/plaintext scope
- 🔧 Implementation notes: the backend remains the final authority for ledger balancing and transfer validation; quick-transfer mode accepts `account_id` + `target_account_id`, keeps the same archived/group checks as standard posting, and records audit entries on each transaction lifecycle transition while preserving the legacy `GET /api/transactions` contract for filters and pagination
- ❌ Tests currently red: none
- 🐞 New defects: none
- 📊 Coverage: backend 86.87% lines (`pytest-cov` gate 85%) · frontend vitest L3 green · full `make test`, `make test-e2e`, and `make lint` green
- 📝 Doc deltas: [04](04-progress.md) ITER-08 row/log closed; no requirement or architecture changes were necessary beyond the supported iteration scope

### ITER-07 — Simple transactions            (status: ✅)
Started: 2026-11-08 · Finished: 2026-11-08

- ✅ ACs completed with tests: **FR-T1–T3 / AC-T1, AC-T2, AC-T3**, **FR-T5 / AC-T5**, and **FR-T9 / AC-T9** verified at API/L3/L4 layers; quick income/expense postings balance server-side, split-line transactions reject any imbalance atomically, the list/filter baseline works with paging, and account numbers are masked in transaction pickers/list payloads without altering encrypted storage boundaries
- ✅ Deliverables: posting service and validation in `backend/app/transactions.py`; protected transaction routes in `backend/app/routers/transactions.py` and registered in `backend/app/main.py`; red-to-green API coverage in `backend/tests/api/test_transactions.py`; minimal transaction UI in `frontend/app/(app)/transactions/page.tsx` and menu wiring in `frontend/app/(app)/mega-menu.tsx`
- 🔧 Implementation notes: the backend remains the authority for ledger balancing; archived or group-type accounts are rejected before insert; category/default-account plumbing from ITER-06 is reused for quick-post flows; memo plaintext remains intentionally unchanged while encrypted account-sensitive boundaries stay stable
- ❌ Tests currently red: none
- 🐞 New defects: none
- 📊 Coverage: backend 87.55% lines (`pytest-cov` gate 85%) · frontend vitest L3 green · full `make test`, `make test-e2e`, and `make lint` green
- 📝 Doc deltas: [04](04-progress.md) ITER-07 row/log closed; [03](03-test-plan.md) T1/T2/T3/T5/T9 matrix note marked covered; [07 §4](07-iterative-prompts.md) rolled to ITER-08 prompt; [05](05-defects.md) close-review refreshed with no new entries; [08](08-backlog.md) untouched (no backlog lifecycle change)

### ITER-06 — Categories            (status: ✅)
Started: 2026-11-08 · Finished: 2026-11-08

- ✅ ACs completed with tests: **FR-K / AC-K1–K4** verified with failing-first category tests at API/L3/L4 layers; starter categories seed idempotently, category CRUD + default-account linkage rules are enforced, transaction-line assignment plumbing works, and category deletion nulls historical references so lines resolve to "(uncategorized)" without deleting history
- ✅ Deliverables: migration and schema wiring in `backend/alembic/versions/0005_categories.py`; category seed+service logic in `backend/app/categories.py`; protected category API routes in `backend/app/routers/categories.py` and `backend/app/main.py`; category API tests in `backend/tests/api/test_categories.py`; minimal category UI in `frontend/app/(app)/categories/page.tsx`; menu + E2E coverage updates in `frontend/app/(app)/mega-menu.tsx`, `frontend/app/__tests__/mega-menu.test.tsx`, and `e2e/smoke.spec.ts`
- 🔧 Implementation notes: delete requires explicit confirmation and clears `transaction_lines.category_id` to `NULL` (reporting as "(uncategorized)"); default-account validation preserves the COA branch rule (`income` categories only link to income accounts, `expense` categories only to expense accounts); crypto/AAD regression battery remains green alongside the category slice
- ❌ Tests currently red: none
- 🐞 New defects: none
- 📊 Coverage: backend 88.83% lines (`pytest-cov` gate 85%) · frontend vitest L3 green · full `make test`, `make test-e2e`, and `make lint` green
- 📝 Doc deltas: [04](04-progress.md) ITER-06 row/log closed; [03](03-test-plan.md) ITER-06 matrix close note added; [06](06-gap-analysis.md) close-of-iteration reality sentence refreshed (no new gaps); [07 §4](07-iterative-prompts.md) rolled to ITER-07 prompt; [05](05-defects.md) close-review timestamp refreshed with no new entries; [08](08-backlog.md) untouched (no backlog lifecycle change)

### ITER-05 — Chart of accounts            (status: ✅)
Started: 2026-11-08 · Finished: 2026-11-08

- ✅ ACs completed with tests: **FR-C / AC-C1–C6** verified through the focused COA API suite and the repo’s regression battery; the app boots with a seeded root tree and re-seeding is idempotent, account creation/edit/archive works through the backend API, and the existing AAD/crypto contract from ITER-04 stays green alongside the new slice
- ✅ Deliverables: COA migration and seed metadata in `backend/alembic/versions/0004_chart_of_accounts.py`; seeded account tree and create/update/archive logic in `backend/app/accounts.py`; protected account routes in `backend/app/routers/accounts.py`; frontend account screen and menu wiring in `frontend/app/(app)/accounts/page.tsx` and `frontend/app/(app)/mega-menu.tsx`; COA API tests in `backend/tests/api/test_accounts.py`
- 🔧 Implementation notes: seed logic merges only newly added accounts; the encrypted `account_sensitive` contract remains ciphertext-only and no plaintext leaks into DB bytes/WAL; the FE scope remains intentionally narrow, staying within account listing + create/edit/archive and not broadening into transactions or reports
- ❌ Tests currently red: none
- 🐞 New defects: none
- 📊 Coverage: backend 88.9% lines (`pytest-cov` gate 85%) · frontend vitest L3 green · E2E smoke remains green; full `make test` + `make test-e2e` pass
- 📝 Doc deltas: [07 §4](07-iterative-prompts.md) rolled to the ITER-06 prompt; [04-progress](04-progress.md) roadmap row marked as closed; no requirement/architecture spec changes were necessary beyond the iteration’s documented scope

### ITER-04 — Encryption core + crypto battery            (status: ✅)
Started: 2026-11-08 · Finished: 2026-11-08

- ✅ ACs completed with tests: **FR-E / AC-E1–E8** verified through the dedicated crypto battery and persistence-contract checks; plaintext never appears in DB bytes or WAL, AAD binding detects cross-entity ciphertext reuse, wrong-key reads fail safely with masking, rotation/backfill updates `active_key_id`, and key selection remains multi-key safe
- ✅ Deliverables: AES-256-GCM encryption service in `backend/crypto/service.py`, keyring management and key rotation in `backend/crypto/keyring.py`, encrypted account-sensitive persistence contract in `backend/app/crypto_store.py` + migration `0003_account_sensitive_contract.py`, and focused contract tests in `backend/tests/unit/test_account_sensitive_contract.py`
- 🔧 Implementation notes: AAD is bound to `a:{table}:{field}:{entity_id}`; old ciphertext can be re-encrypted during rotation without leaking plaintext; keyring env/file state is synchronized to avoid stale reads after rotation; the crypto iteration intentionally stops at the storage contract and does not broaden into COA CRUD or UI work
- ❌ Tests currently red: none
- 🐞 New defects: none
- 📊 Coverage: backend 94% lines (`pytest-cov` gate 85%) · frontend vitest L3 green · E2E smoke remains green; crypto battery passes E1–E8
- 📝 Doc deltas: [03](03-test-plan.md) encryption row notes marked as tested; [07 §4](07-iterative-prompts.md) rolled to ITER-05 prompt

### ITER-03 — User management            (status: ✅)
Started: 2026-11-08 · Finished: 2026-11-08

- ✅ ACs completed with tests: **AC-U4a** authenticated users list + frontend Users screen showing username/display/active/created/last-login fields; **AC-U4b** deactivate path bumps `session_epoch` and revokes existing sessions on next request; **AC-U4c** last-active refusal enforced on deactivate/delete attempts; **AC-U4d** own-password change requires old password, writes argon2id hash, and refreshes session cookie without logout; **AC-U4e** `/api/users` remains authenticated-only (401 when unauthenticated)
- ✅ Deliverables: backend user-management API routes (`GET /api/users`, `PATCH /api/users/{id}`, `DELETE /api/users/{id}` soft-delete semantics, `PATCH /api/users/me/password`) in `app/routers/users.py`; user-management service logic in `app/auth.py` including revocation/guards/password update; migration `0002_users_last_login` + login touch of `last_login_at`; frontend `/users` screen (list/edit/activate/deactivate/soft-delete + own-password change) and mega-menu Users destination enabled
- 🔧 Implementation notes: per user clarification, delete uses soft-delete (`is_active=0`) and self deactivate/delete is refused; to satisfy both this rule and AC-U4c, last-active self operation returns conflict, while non-last-active self operation returns forbidden; auth generic failure behavior for inactive users remains unchanged
- ❌ Tests currently red: none
- 🐞 New defects: none
- 📊 Coverage: backend 94% lines (`pytest-cov` gate 85%) · frontend vitest L3 green · E2E now 3-scenario smoke including user-management flow
- 📝 Doc deltas: red snapshots captured under `docs/logs/iter-03/red-backend.log`, `docs/logs/iter-03/red-frontend.log`, and `docs/logs/iter-03/red-e2e.log`; [03](03-test-plan.md) ITER-03 matrix note appended; [07 §4](07-iterative-prompts.md) rolled to ITER-04 prompt

### ITER-02 — Auth core            (status: ✅)
Started: 2026-11-08 · Finished: 2026-11-08

- ✅ ACs completed with tests: **AC-U1a–U1d** register + duplicate + validation + 10-minute registration throttle; **AC-U2a–U2d** login success/failure, generic inactive handling, timing-equal check, 15-minute lockout, auth-page redirect behavior; **AC-U3a–U3b** logout cookie clear + stale/invalid session 401 handling; **NFR-2** `/api/**` guard matrix with exact exempt set (`/api/auth/register`, `/api/auth/login`, `/api/healthz`); **AC-N1–N4 partial / AC-N2 minimum** mega-menu shell with Dashboard/Reports links, disabled coming-soon groups, keyboard close (Escape), and route highlight
- ✅ Deliverables: first real Alembic migration creating `users` table (`backend/alembic/versions/0001_users_auth_core.py`); backend auth stack (`/api/auth/register|login|logout|me`) with argon2id, JWT HS256 cookie (`investflow_session`, httpOnly, SameSite=Lax), `session_epoch` claim and epoch revocation check; CSRF header enforcement on mutating `/api/**`; frontend `/login` + `/register` pages with client-side validations mirrored to server constraints; server-side auth gate in `(app)` layout redirecting to `/login`; L4 flow updated to register→dashboard→logout→login
- 🔧 Implementation notes: throttle/timing tests use pinned `time-machine` clock (no sleeps); auth middleware now executes before routing so unknown protected `/api/**` paths still return 401 as required; Playwright backend boot now runs `alembic upgrade head` before uvicorn to keep fresh environments migration-safe
- ❌ Tests currently red: none
- 🐞 New defects: none
- 📊 Coverage: backend 96% lines (`pytest-cov`, gate 85%) · frontend vitest coverage provider wired (`@vitest/coverage-v8`) per GAP-008
- 📝 Doc deltas: red snapshots stored under `docs/logs/iter-02/red-backend.log` and `docs/logs/iter-02/red-e2e.log`; [06](06-gap-analysis.md) GAP-008 closed; [07 §4](07-iterative-prompts.md) regenerated to ITER-03 handoff prompt

### ITER-01 — Project skeleton & CI            (status: ✅)
Started: 2026-11-08 · Finished: 2026-11-08

- ✅ ACs completed with tests: **NFR-1** — README quickstart is exactly 2 commands (`make setup`, `make dev`, then open :3000); dev target starts both processes, verified by the stacked-real-stack E2E run · **NFR-6** — `ruff format --check` + `ruff check` clean, `mypy --strict app` clean (7 files), eslint flat + `tsc --noEmit` clean; backend coverage 100% of the skeleton (39 stmts) · **NFR-11** — pragmas WAL/`foreign_keys=ON`/`busy_timeout=5000` asserted on every connection by L1 tests; versions pinned via `uv` lock (`.python-version` → 3.12) + `pnpm` lockfiles
- ✅ Deliverables: `GET /api/healthz` → `{"status":"ok","version":"0.1.0"}` covered at L2 (`tests/api/test_healthz.py`) + L4 smoke; SQLite connection layer (`app/db/connection.py`); Alembic initialized (empty root migration, env.py wired to `INVESTFLOW_DB_PATH`/default and applies the same pragmas — WAL verified on the migration path); Next.js shell `/`→`/dashboard` placeholder + Tailwind 4/DaisyUI 5 (`globals.css @plugin "daisyui"`); Makefile targets `setup/dev/test/test-e2e/lint/migrate` (+ `dev-backend`/`dev-frontend` helpers); lint/type configs CI-runnable — `.github/workflows/ci.yml` (backend / frontend / e2e jobs, user-approved addition)
- 🔧 Implementation notes: TDD honored — all three harnesses were red before code (fail snapshots below); Playwright webServer array boots uvicorn(:8000)+next dev(:3000); readiness URL must 2xx → configured to poll `/`; vitest harness pinned as a matched set: `vitest@3.2.7` + `vite@7.3.7` + `@vitejs/plugin-react@5.2.0` (v6 requires vite 8, incompatible with vitest 3 — pin recorded here as harness truth); tests assets: red snapshots committed under `docs/logs/iter-01/red-*.log` (recorded per [03 §8.1](03-test-plan.md))
- ❌ Tests currently red: none
- 🐞 New defects: DEF-001, DEF-002 (S3, CI-only pnpm issues found in post-close Actions runs — both fixed same day, see [05](05-defects.md))
- 📊 Coverage: backend 100% (39/39 stmts, pytest-cov) · frontend: vitest harness ready, coverage **provider not yet wired** → GAP-008
- 📝 Doc deltas (R4): [02 §2](02-architecture.md) layout + `e2e/` + root `package.json` + Makefile target list updated (ADR-005) · [03 §4](03-test-plan.md) note that ITER-01 closed with healthz smoke mapping · [06](06-gap-analysis.md) GAP-008 · [07 §4](07-iterative-prompts.md) regenerated for ITER-02 (ADR-005 covers the only spec-touch, no D-xx change → [00](00-overview.md) untouched per R6)
- 🕸 Watch item (not a defect): Starlette emits a TestClient/httpx deprecation warning upstream ("install httpx2") — revisit at ITER-02 to avoid accumulating tech debt while NFR-2 cookie tests are written

## 4. ADR-log (architecture decision records raised during dev)

| ADR | Date | Decision | Reason | Doc |
|---|---|---|---|---|
| ADR-001 | 2026-11-08 | App-layer field encryption over SQLCipher (D-11) | field-level audit + masking flexibility; key rotation per field | [02 §4.4](02-architecture.md) |
| ADR-002 | 2026-11-08 | Ledger not auto-revalued; holdings valued at report time (D-07) | keeps double-entry strict; avoids synthetic value entries | [01 §5](01-requirements.md) |
| ADR-003 | 2026-11-08 | Categories as separate tag entities, not income/expense COA leaves | supports both COA and category grouping in cash-flow reports | [01 §3](01-requirements.md), [02 §3.1](02-architecture.md) |
| ADR-004 | 2026-11-08 | Session revocation via `session_epoch` counter claim | simple, DB-driven logout/deactivation invalidation | [02 §4.3](02-architecture.md) |
| ADR-005 | 2026-11-08 | Monorepo gains `e2e/` (Playwright L4) + root `package.json` (Playwright test runner home) + `.github/workflows/ci.yml`; toolchain realized as uv + Python 3.12 pin, pnpm, vitest 3.2.7, Playwright 1.x, Next 15.5/React 19.1, eslint 9 flat | [03 §2](03-test-plan.md) places L4 at repo-root `e2e/**` and the user approved a minimal GH Actions workflow; layout in [02 §2](02-architecture.md) updated, spec-level D-16 floors unchanged | [02 §2](02-architecture.md) |
| ADR-006 | 2026-11-08 | User delete is implemented as soft-delete (`is_active=0`) and self deactivate/delete is denied | preserves user-history rows while still satisfying revocation and last-active protections; aligns with shared-book continuity expectations | [01 §1 FR-U4](01-requirements.md), [02 §3.1](02-architecture.md) |
| ADR-007 | 2026-11-10 | FR-X4b submenu labels **supersede** FR-X3b (`Investments → Portfolio/Analysis/Research`, `Settings → Backup and Downloads`); FR-X3 keeps original record as the superseded draft | the implemented navbar follows FR-X4 (verified by L3/L4 in ITER-21); resolves the X3b/X4b AC contradiction recorded in [01 §12](01-requirements.md) without changing routes or auth | [01 §12](01-requirements.md), [02 §5.2](02-architecture.md) |
| ADR-008 | 2026-11-10 | Portfolio CSV import (FR-IMP-1): buy/sell trade rows update **positions only** through the avg-cost engine (no ledger legs — positions live inside brokerage accounts per D-08, so trade cash flows belong to the mapped brokerage account); dividend/fee rows post real two-leg transactions through the posting service (cash leg + seeded `Interest & Dividends`/`Fees` COA leaf, hash stored as `reference` `import:<hash16>`); import adds staging tables `import_mappings`/`import_batches`/`import_rows` (spec addition to 02 §3.1) with the `import_rows` hash registry enabling re-import dedupe | keeps net-worth double-count-free (ledger basis never overlays holdings value), reuses the existing posting service as the only route to `transaction_lines` (T-1), and makes whole-file atomicity possible on a single connection; refines the backlog §3C wording that implied full double-entry trade legs | [01 §12](01-requirements.md), [02 §3.1](02-architecture.md), [02 §4.5](02-architecture.md) |
| ADR-009 | 2026-11-10 | Price-history import (AC-IMP1h, ITER-23): the *bank statement* starter template is repointed to the price-history shape (`Date/Ticker/Close/Volume` — its ITER-22 bank-statement-shaped columns were invalid for the `price_history` kind and would 422); price rows are **not account-bound**; commit upserts `price_cache` on the unique `(ticker, date)` key with `source='manual'` (never duplicate rows) and refreshes `latest_quotes` with the newest imported close per ticker (`asof` = the close date at midnight UTC so the stale badge shows the true price date); dedupe uses a price-row hash registry `(date, ticker, close_q4, volume)` — identical re-imports are duplicate-skipped, corrected closes re-post and upsert; price history writes **no ledger rows** | resolves a shipped-template inconsistency proven by the red tests; honest `asof` keeps AC-I2b stale-badge semantics truthful while AC-I2c manual precedence (`resolve_quote` serves manual quotes before staleness checks) is unaffected; reuses the importer core (no second parser) per the ITER-23 traps | [01 §12](01-requirements.md), [02 §3.1](02-architecture.md), [08 §3C](08-backlog.md) |
| ADR-010 | 2026-11-11 | FEAT-002 (non-investment opening balances + statement migration import, [08 §3D](08-backlog.md)) is **promoted into `01-requirements.md` §12 FR-IMP-2 (AC-IMP2a–IMP2i)** and **scheduled as ITER-24** (user instruction); it shares the FR-IMP-1 importer core, mapping-template system, and import staging tables (ADR-008), posts exclusively through the posting service (T-1), and adds `transactions.import_batch_id FK→import_batches NULL` as import provenance (02 §3.1 spec addition to be applied with ITER-24 tests); reverse-batch = staged `void`, never mass-delete | completes the full "migrate from my previous app / bank statements" path pair (FEAT-001 + FEAT-002) per 08 §3D.7; one wizard, two tabs (Q-10); scheduling is the user's call per the backlog lifecycle | [01 §12 FR-IMP-2](01-requirements.md), [08 §3D](08-backlog.md) |

*(Append rows as decisions arise — never rewrite history rows.)*

## 5. Iteration ↔ requirement-versioning adjustments

| Iter | Requirement doc sections touched | Architecture doc sections touched |
|---|---|---|
| 1 | — (no requirement sections touched; only README/quickstart surfaces) | 2 (layout, Makefile target list), 7 (ops refs used as basis — no edit needed) |
| 2 | FR-U1–U3, FR-N, NFR-2 | 4.3, 5.1, 5.2 |
| 3 | FR-U4 | 3.1 users |
| 4 | FR-E | 4.4, 6 |
| 5 | FR-C | 3.1 accounts/account_sensitive, 3.3 seed, 5.1 |
| 6 | FR-K | 3.1 categories |
| 7 | FR-T1–T3, T5, T9 | 4.5 |
| 8 | FR-T4, T6–T8, T10 | 4.5, 3.1 audit_log |
| 9 | FR-R1–R4, R9/R10, NFR-9 | 4.8 |
| 10 | FR-R5–R8, NFR-4 | 4.8, 4.9/exports |
| 11 | FR-D, FR-N | 5.1/5.3 |
| 12 | FR-I1, I3 | 4.6, 3.1 positions |
| 13 | FR-I2 | 4.9 providers |
| 14 | FR-I3/I4/I5 | 4.6 ta |
| 15 | FR-I6/I7 | 4.7 |
| 16 | FR-S, NFR-7 | 7, 2 |
| 17 | FR-X1 | 5.4 |
| 18 | FR-X2 | 5.4, 5.3 |
| 19 | FR-X3, FR-N | 5.1, 5.2 |
| 20 | FR-X4, FR-N | 5.1, 5.2 |
| 21 | FR-X4, FR-N, NFR-7 (regression gates) | 5.1, 5.2 (interaction model; no structural change) |
| 22 | FR-IMP-1 | 3.1 (import_mappings/import_batches), 4.5 (posting service reuse), 5.1 (route `/investments/import`), 5.2 (Investments submenu wiring) |
| 23 | FR-IMP-1 (AC-IMP1h) | 3.1 (price_cache + import staging price_history semantics) |
| 24 | FR-IMP-2 (AC-IMP2a–IMP2i) | 3.1 (transactions provenance column + import staging reuse), 4.5 (posting service) — *(expected; update on finish)* |

(served as "expected bootstrap" so sessions know exactly which docs the next iteration touches;
update real rows on finish.)
