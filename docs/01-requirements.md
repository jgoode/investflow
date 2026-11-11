# InvestFlow — 01 · Requirements

| | |
|---|---|
| **Status** | Active |
| **Last updated** | 2026-11-10 (ITER-23: FR-IMP-1 AC-IMP1h landed — FR-IMP-1 complete per ADR-009) |
| **Parent** | [00-overview](00-overview.md) |

Requirement IDs: `FR-<area><n>` functional, `NFR-<n>` non-functional, `AC-<id>` acceptance criteria (Given/When/Then).
Each FR is **testable**; [03-test-plan](03-test-plan.md) maps FR → test layer → iteration.

Every user-visible amount is rendered with the currency label from Settings (default `USD`);
amounts are **integers in cents** end to end.

---

## 1. Auth & Users (FR-U)

Shared book, single role, open self-registration. Unauthenticated access is impossible; see NFR-2.

### FR-U1 — Registration
Self-service account creation from the **Registration screen**. Fields: username (3–32, `^[a-z0-9._-]+$`),
display name (optional), password (min 10 chars, must not equal username), password confirmation.

- **AC-U1a** — *Valid registration*. Given no user `alice` exists, When the user registers `alice` with a valid password, Then a user record is created (hashed with argon2id), the user is logged in immediately, and the Home dashboard is shown.
- **AC-U1b** — *Duplicate username.* Given `alice` exists, When registering `alice` again, Then an inline error "username already taken" is shown and no user is written; the entered password is not retained.
- **AC-U1c** — *Validation.* When a password shorter than 10 chars, a username with spaces/uppercase, or mismatched confirmation is submitted, Then field-level errors are shown before any request mutates state.
- **AC-U1d** — *Rate limiting.* When ≥5 registrations complete from the same session within 10 minutes, Then further registration attempts are refused with HTTP 429 for the window.

### FR-U2 — Login
The **Login screen** authenticates by username + password and establishes the session cookie *(NFR-2)*.

- **AC-U2a** — Given a valid, active account, When correct credentials are submitted, Then the user is redirected to the Home dashboard.
- **AC-U2b** — Given an inactive user, When correct credentials are submitted, Then a generic failure message is shown. *(Do not reveal that the account is inactive.)*
- **AC-U2c** — Given wrong username or password, When submitted, Then the same generic failure appears after a deliberately slowed comparison (timing-equal). After 5 consecutive failures the account's login attempts are throttled for 15 minutes (per-user, in-memory).
- **AC-U2d** — Given an authenticated session, When the user opens `/login` or `/register`, Then they are redirected to the dashboard.

### FR-U3 — Logout
- **AC-U3a** — Given any authenticated screen, When the user clicks Logout in the mega menu, Then the session cookie is cleared, the audit trail records the event, and `/login` is shown.
- **AC-U3b** — Given a stale/expired/invalid JWT cookie, When any API call is made, Then the API returns HTTP 401 and the frontend routes to `/login`.

### FR-U4 — User management
Every user can view and manage fellow users (shared book, all equal): list, edit display name, change own password, set **active/inactive**, and delete a user **only if not the last active user**.

- **AC-U4a** — Given users exist, When the Users screen is opened, Then all users are shown with username, display name, active state, created date, and last login (if known).
- **AC-U4b** — When a user is set **inactive**, Then that user's active sessions are revoked (their next API call returns 401).
- **AC-U4c** — When the last active user would be deactivated or deleted, Then the action is refused with an explanatory error.
- **AC-U4d** — When a user changes their own password, Then the old password is required, the new one is argon2-hashed, all other fields are untouched, and the session is refreshed without logging out.
- **AC-U4e** — User records are listed/edited only through the Users screen; user enumeration via the API requires authentication (no public user list).

---

## 2. Chart of accounts (FR-C)

Tree of accounts: root types **Asset, Liability, Income, Expense, Equity** (fixed). Ships with a **seeded standard COA** (see [02-architecture](02-architecture.md) §3.3) that is fully **editable**: accounts may be added, renamed, moved within type, archived, or marked as investment (brokerage).

Account fields: `code` (unique, user-assigned, free-form), `name`, `type`, `parent`, `subtype` (ordinary, brokerage/investment, credit card, bank, cash, fund), `institution`, `description`, `is_archived`, `is_investment`.
Sensitive detail fields (see FR-E): account number, routing/transit, transfer instruction numbers, notes — stored **ciphertext only**.

- **AC-C1** — *Seed on first run.* Given a fresh database, When the app or migration initializes, Then the standard seed COA exists exactly once, and re-running the seed is idempotent (no duplicates).
- **AC-C2** — *Create account.* Given the Accounts screen, When a valid account is created under an Asset parent, Then it appears in the tree with computed balance 0 and appears in posting pickers.
- **AC-C3** — *Type inheritance.* When creating/moving an account, Then its effective type always equals its root-type branch; an Asset account can never end up under Liability. The UI enforces and the API rejects (HTTP 422).
- **AC-C4** — *Archive semantics.* When archiving an account holding open positions or a non-zero balance, Then a confirmation dialog demands explicit consent; archived accounts are hidden from posting and reporting drop-downs but remain in the COA tree (greyed) and in historical reports.
- **AC-C5** — *Balance integrity.* Given any account, its displayed balance always equals Σ debit − Σ credit over its ledger lines (+ Σ market value of holdings for investment accounts). A dedicated test recomputes all balances from lines and compares with report output.
- **AC-C6** — *Placeholder enforcement.* Groups (parents) accept only child accounts; leaf accounts accept transaction lines. Creating a posting against a group account is rejected (422).

## 3. Categories (FR-K)

Categories are a **free-form tag set** (income or expense) assignable per transaction line, and each category may declare a *default account* used to pre-select posting targets in the transaction UI.

- **AC-K1** — Given empty categories, When a new book initializes, Then a starter income/expense category set is created (idempotent).
- **AC-K2** — When a category is assigned to a transaction line, Then that line's cash-flow/category report row aggregates under it; lines without a category report under "(uncategorized)".
- **AC-K3** — When a category is deleted, Then lines referencing it are set to "(uncategorized)" — history is never destroyed; deletion requires confirmation.
- **AC-K4** — Category colors/names are editable; renames propagate instantly across reports (no stale cached labels).

## 4. Transactions (FR-T)

Simple posting surface on a rigorous ledger. A transaction has: date, description, reference (optional), status `posted|void`, lines `{account, direction, amount, memo?, category?}`. The UI offers comfortable modes but the invariant is strict:

- **Invariant T-1** — Σ debits = Σ credits per transaction, exactly, before storage. API rejects any imbalance (422).
- **Invariant T-2** — Posting to an archived or group account is impossible.
- **Invariant T-3** — Dates allow the past and up to today's date; future-dated posting is rejected by default (setting can extend the window ≤ 30 days).

- **AC-T1** — *Quick post (expense).* Given a transaction entry form with mode "expense", When the user picks a liability/bank account, an expense category (→ account), enters `-`-free amount and description, Then the backend receives two lines (debit expense / credit bank) and posts atomically.
- **AC-T2** — *Quick post (income).* Mirror of AC-T1: debit bank / credit income account.
- **AC-T3** — *Advanced entry.* When the split/split-lines editor is used with N lines, Then the form shows an off/on-by balance and blocks submit until it is exactly 0 (client) — the API checks server-side as final authority.
- **AC-T4** — *Transfer.* When posting a transfer between bank A (debit) and bank B (credit) of amount X, Then exactly two lines exist, bank balances change by ±X, and neither was an income/expense account.
- **AC-T5** — *List & filter.* The transaction list supports paging (20/page), and filtering/ranging by date, account, account types, category, amount min/max, and free-text. Default view: last 90 days, newest first. Filter changes are shareable via URL query params.
- **AC-T6** — *Edit.* Editing a transaction replaces its lines fully and keeps one audit entry; a voided transaction cannot be edited (only un-void → edit).
- **AC-T7** — *Void, not delete.* Delete does not exist; void marks lines non-contributing (`status=void`), keeps the ledger trace, requires confirmation, and reports exclude void transactions by default with a historical toggle to include them.
- **AC-T8** — *Running balance.* The transaction list shows a per-account running balance when a single-account filter is active.
- **AC-T9** — *Account-number masking.* When a transaction references an account in a dropdown or list, the dropdown traps focus within the menu; Escape closes the menu and focus returns to the trigger.
- **AC-T10** — *Encryption integration.* When a payee/bank detail (e.g., transfer reference) is attached as transaction memo, Then it is stored as ordinary ledger text; only account-record sensitive fields are encrypted (scope enforced by FR-E), keeping the memo visible to all users by design with no alternate edit path.

## 5. Investments (FR-I)

Positions live **inside** investment accounts (COA, see AC-C). No auto-revaluation entries are posted to the ledger; market value is computed at read time.

### FR-I1 — Positions & average cost
- **AC-I1a** — *Buy.* When a buy of N shares of ticker T at price P with fee F posts into brokerage account A, Then a position row (account A, T) is created/updated, quantity N is held, and average cost = (prior qty × prior avg cost + N×P + F) ÷ (prior qty + N).
- **AC-I1b** — *Sell.* When M shares of T sell in account A at price P, Then realized P&L = M×P − M×avg_cost (average-cost method), the position reduces quantity M, ledger lines post the cash movement (+fees) with a realized-gain income line, and fully-cleared positions move to a "closed" view with realized P&L retained.
- **AC-I1c** — *Quantity/price precision.* Quantities are stored as integers scaled ×10⁴ (4 decimals); prices ×10⁴; no floating-point drift occurs across repeated buys/sells (property test included).
- **AC-I1d** — *Oversell blocked.* When selling more than the position quantity, Then the API rejects (422).

### FR-I2 — Market data (Yahoo Finance, unofficial)
Provider adapters isolate the app; Yahoo is the first adapter. Quotes and daily history are cached (`price_cache`).

- **AC-I2a** — When a position's market value is requested and a cached quote for T is fresher than **15 min**, Then the cache serves it and no provider call happens (observable in mock/recorded test).
- **AC-I2b** — When the provider is unreachable or returns malformed data, Then the UI shows price age badge ("stale, last price @ time") and the app continues to work with manual-entry prices; no crash, no partial state.
- **AC-I2c** — When the user manually enters a price for T (manual fallback screen), Then it overrides the cache until any newer provider quote arrives (a manual price is tagged `manual`, manual entry always preserved as fallback).
- **AC-I2d** — *Rate limit discipline.* Provider polling is user-triggered or ≤1 request/quote/15 min background refresh; Yahoo terms are respected; relevant disclaimers ("data via Yahoo Finance, unofficial, no SLA") appear on investment screens.

### FR-I3 — Position detail & info
Position screen per holding: quantity, avg cost, market price (stale visibly marked, *AC-I2b*), market value, unrealized P&L, 1D/1Y return, sparkline of price history, and a company-info card (name, sector, exchange — from provider profile).
**AC-I3a** — Given positions in ≥2 accounts, When the Positions page is opened, Then holdings are grouped by account with subtotals and an overall total, sorted by market value desc.

### FR-I4 — Position news
- **AC-I4a** — When news is requested for T, Then the provider adapter fetches company news items (title, source, URL, summary, published), rendered newest-first with source links opening in a new tab (`rel="noopener"`).
- **AC-I4b** — Given network failure or empty news list, Then a friendly empty/error state appears; latest-good cached news is used when available (cache ≤ 30 min).

### FR-I5 — Technical analysis (baseline set)
Indicators over daily close prices for a position's ticker: **SMA(20, 50, 200), EMA(12, 26), RSI(14), MACD(12,26,9), Bollinger Bands(20, 2), volume bars**. User-visible parameters for SMA/EMA periods (validated within 2–250).
- **AC-I5a** — Given ≥ required lookback of daily closes, When the technical view is opened, Then each indicator renders an overlay/secondary graph aligned by date with a legend (lightweight-charts below the Recharts price series or equivalent).
- **AC-I5b** — Given insufficient history (fewer points than lookback), Then the indicator is labelled "insufficient data" instead of being drawn incorrectly.
- **AC-I5c** — Indicator implementations are validated against a reference fixture (e.g., pandas-ta output on known data) with ≤1e-6 tolerance — dedicated unit tests.

### FR-I6 — Portfolio analysis
- **AC-I6a** — When the Portfolio page opens, Then it shows: total market value per account and total, asset allocation by account and by ticker/currency-exposure, current weights with a target-input panel, and **cash share** per brokerage account.
- **AC-I6b** — Return timeline: portfolio value over trailing 1M/3M/6M/1Y built from cached daily closes + cash balances, rendered as an area chart with time-range toggles.
- **AC-I6c** — Risk metrics: annualized return & volatility (std of daily returns ×√252), Sharpe (rf configurable, default 0.02), max drawdown, beta vs a benchmark ticker (default SPY) — all computed from cached history and unit-tested against a fixture.

### FR-I7 — Portfolio optimization (mean-variance)
- **AC-I7a** — Given cached history (≥ 120 trading days) for all tickers in scope, When the user clicks Optimize, Then the system computes annualized expected returns and covariance, and renders: (a) current weights vs **max-Sharpe** weights, (b) current vs **min-variance** weights, and (c) an efficient frontier curve (≥ 30 points) with the current portfolio marked.
- **AC-I7b** — Optional constraint fields: min/max weight bounds (0–100% per asset), exclusion list — the optimizer respects them or reports infeasibility clearly.
- **AC-I7c** — Given < 120 days of history for any ticker, Then the optimizer explains the shortfall and offers to exclude those tickers from scope.
- **AC-I7d** — Optimization is advisory-only; it never trades or posts. A disclaimer states that outputs are based on historical variance and are not advice.

## 6. Reporting (FR-R)

All reports support date ranges with sensible defaults, exclude void transactions unless toggled, and can be exported to **Excel (xlsx)** and **PDF**. Each report is reachable from the Reports mega menu **and** from dashboard drilling (FR-D). Rendering server-side first (deterministic tables), then graphs.

- **AC-R1** — *Chart of accounts report.* Lists every account (incl. archived, flagged) with type, code, name, balance as of a date; grouped and subtotaled by type; assets − (liabilities + equity) = 0 invariant.
- **AC-R2** — *Summary (income statement).* Revenue/income accounts and expense accounts over the range with totals, category grouping, and resulting surplus/deficit.
- **AC-R3** — *Monthly report.* Per-calendar-month rows of income, expense, net (cash flow), plus top 5 expense categories per month, selectable months, and optional accounts sub-report.
- **AC-R4** — *Quarterly report.* Same shape as monthly, aggregated per quarter (Q1–Q4, year selector).
- **AC-R5** — *Cash flow statement.* For the range: opening net liquid balance, inflows/outflows grouped by category + large single transfers shown separately, closing balance; daily-precision when range ≤ 62 days, weekly otherwise.
- **AC-R6** — *Net worth statement.* Time series of net worth (assets incl. holdings valued from price cache at that date − liabilities), table + stacked area graph, drill-in to asset/liability composition at any displayed month-end.
- **AC-R7** — *Excel export.* Export produces a styled workbook (heading row, column widths, frozen header, correct integer-cents → decimal conversion) matching on-screen data within tolerance 0; filename `investflow-<report>-<from>-<to>.xlsx`.
- **AC-R8** — *PDF export.* A4, repeatable header/footer page numbering, same numbers as on-screen (cross-check ≥ decimal 2), filename pattern as FR-R7; renders identical date ranges and filters.
- **AC-R9** — *Report caching.* Report parameters are URL-encoded; refreshing shares the same output. No stale-cache layer — each report always computes fresh (acceptable at this scale).
- **AC-R10** — *Historical integrity.* All reports derive from the ledger (`transaction_lines`); a test re-derives monthly income from raw lines and compares with the monthly report.

## 7. Home dashboard (FR-D)

Dashboard-first layout focusing on **cash flow** and **net worth**. Real-time enough to keep useful data visible; layout configurable by the user (drag-and-drop or toggles, saved per user [NFR-7]).

- **AC-D1** — Cards visible on load: Net worth (current value + Δ% over trailing window), Cash flow this month vs last month, Income/expense mini-bars for trailing 6 months, Portfolios holdings value, Recent transactions (≤5), Accounts at-a-glance by type with balances.
- **AC-D2** — *Drill-down* — every chart/card/table card supports right-click (context menu) and double-click to: show report in same screen with the exact date range applied (deep-link to Reports), open the underlying screen, or copy a CSV of the current data.
- **AC-D3** — All dashboard queries are ≤ 2 worker-bound API requests on first paint (backend batch endpoint or parallel fetch) and P95 < 500 ms for a 10k-transaction book benchmark (NFR-4).
- **AC-D4** — Dashboard reflects server current state on refresh: every card refetches on load with no hidden cache layer (no stale values shown).
- **AC-D5** — Empty state languages: first-run book (0 accounts, 0 transactions, 0 positions, starter COA seeded) shows onboarding hint cards per section.

## 8. Settings (FR-S) — "Recommended + admin extras"

Single screen, sectioned mega-menu entry; all read from/written to the `settings` table (typed key-value) plus per-user preferences.

- **AC-S1** — *Profile*: view/edit display-name, change own password (same rules as FR-U1 rules, old password check).
- **AC-S2** — *Currency & regional display*: currency label/symbol (default USD, free allowance), first day of the week, month-reported end-of-day rounding mode (floor/round-half-up).
- **AC-S3** — *Market-data provider*: select adapter from registry (Yahoo active, others disabled with "later"), edit stored API access token (Yahoo needs none/tokens flow later), test-connection button showing last successful fetch + explicit "unofficial, no SLA" disclaimer.
- **AC-S4** — *Posting defaults*: default transaction posting window (0–30 days future allowance), default quick-entry accounts, default category per transaction type; applied on new transaction form.
- **AC-S5** — *Seed COA management (admin extra)*: view seed package version, preview and **apply/re-apply** idempotent seed additions, view seed diff before apply; existing user edits to seeded accounts are never overwritten silently.
- **AC-S6** — *Backup / restore helpers (admin extra)*: (a) Export JSON settings snapshot; (b) generate SQLite backup file (`sqlite3 .backup` semantics) downloadable from the UI with a confirmation ribbon; (c) restore-from-backup **not** exposed in v1 — download only, restore documented as manual (gap analysis). Backup goes through a transactionally-consistent snapshot to avoid mid-write corruption.
- **AC-S7** — *Audit log viewer (admin extra)*: paginated log of user actions (type, entity, user, timestamp, summary); sensitive detail values are masked, never decrypted into the log; filters by user, action type, date range.
- **AC-S8** — Settings changes are audited (action `settings.update`), invalid values rejected with inline field errors, and rate-limited writes protect accidental flooding.

## 9. Encryption at rest (FR-E)

Frames the storage contract for sensitive fields on `accounts` (and future entities registered in the cipher registry). AES-256-GCM via app-layer field encryption; SQLite file stays plain (D-11).

- **AC-E1** — Given the encrypted-at-rest registry lists `accounts.account_number_enc`, `accounts.routing_enc`, `accounts.transfer_numbers_enc`, `accounts.notes_enc`, when anything is written to those columns, Then the persisted byte payload is **non-deterministic ciphertext** (unique per write, nonce-randomized) — a DB-scan test asserts no plaintext of known account numbers appears anywhere in the SQLite file.
- **AC-E2** — *AAD binding.* Ciphertexts bind to `(entity_type, entity_id, field, key_id)` as AES-GCM AAD; moving/renaming IDs cannot be cross-pasted between accounts or columns without failing decryption.
- **AC-E3** — *Survives restart.* Given encrypted values exist, when the backend restarts with the same key material, Then the values decrypt and are rendered correctly; frontend receives them only from **already-decrypted API responses**, over HTTPS/localhost only.
- **AC-E4** — *Key management.* Key material lives outside the DB: env var `INVESTFLOW_ENC_KEY` or a key file path; first-boot generates and writes a key file with mode 0600 if neither is set. A **key-rotation procedure** (versioned key IDs `v1`, `v2`, …; re-encrypt-through-backfill job decrypt-old/encrypt-new, verified by counts) is documented, tested as a unit path, and available as an admin action.
- **AC-E5** — *Never logged.* Decoder logs never include plaintext; logging library filter tests verify this for the account-crypto path (all log output asserted ciphertext-safe).
- **AC-E6** — *Masking.* UI shows `•••3421` style last-4 derived from **plaintext** at write time (plain `last4` column), toggle-reveal requires a fresh click each time (no persisted reveal), and clipboard-copy of decrypted values is enabled only with an explicit user confirmation per event.
- **AC-E7** — *Encrypted import/export.* XLSX/PDF exports mask sensitive fields with `•••` by default and require an explicit per-export toggle (default off) to include readable values; encrypted fields are never silently included in JSON settings backups (exception-listed, vowels masked or omitted).
- **AC-E8** — *Change-visibility.* Admin extras can run a "decrypt-and-verify" diagnostics to show record-level integrity counts (how many ciphertexts decrypt OK vs errors) without printing contents to screen or logs.

## 10. Mega menu & navigation (FR-N)

Top bar with the classic mega menu; keyboard accessible, mobile-collapsed into sections.

- **AC-N1** — Menu groups: **Dashboard · Accounts · Investments · Reports · Users · Settings**. Top-level groups contain flyout columns of pages with descriptions, and (Accounts/Investments/Reports only) a right column with "recent" links per user.
- **AC-N2** — Keyboard accessible: All interactive elements reachable by Tab in a logical order; Enter/Space activate buttons and links; Escape closes the mega menu with focus returned to the trigger.
- **AC-N3** — Mobile: menu collapses into grouped, scrollable sections (no horizontal overflow, no hover-only content, touch-friendly hit areas ≥ 44px).
- **AC-N4** — Active-state highlight follows the current route (single group open). Breadcrumb/URL remain the source of truth after refresh.

## 11. Non-functional requirements (NFR)

| ID | Requirement | Acceptance signal |
|----|-------------|-------------------|
| **NFR-1** | **Local web app.** `make dev` (or platform-equivalent scripts) starts backend and frontend; user opens `http://localhost:3000`. Single-machine assumption documented; no cloud-only features. | Dev-quickstart with ≤ 3 commands |
| **NFR-2** | **Authentication & sessions.** JWT (HS256) in `httpOnly; SameSite=Lax; Secure` cookie; 12 h expiry; server may early-invalidate (AC-U4b). All `/api/**` except `/api/auth/register`, `/api/auth/login`, `/api/healthz` require a valid session. | Playwright + API tests |
| **NFR-3** | **Security of secrets & PII.** Passwords argon2id; sensitive fields encrypted (FR-E); login failure messages generic + timing-equal; cookies `Secure` and `httpOnly`; no secrets in client bundles; CSRF protection via SameSite + `X-Requested-With` header check on state-changing requests. | Security test suite §5.4 |
| **NFR-4** | **Performance.** Book up to 50k transaction lines and 5 years of daily price points must remain responsive: dashboard P95 < 500 ms, standard reports P95 < 2 s, transaction list page < 300 ms (Xeon-class dev laptop, SQLite). Index strategy documented in [02](02-architecture.md). | Benchmark suite §5.5 |
| **NFR-5** | **Reliability.** All writes transactional; the provider outage path leaves the app fully functional (AC-I2b); SQLite backups via Settings are crash-consistent (AC-S6). | Chaos/rollback tests |
| **NFR-6** | **Code quality.** Python: ruff + mypy strict (backend package), coverage ≥ 85% (≥ 95% for `crypto/`, `money/`, `portfolio/` packages). TypeScript: strict mode, eslint flat config, no `any` leaks across API boundary, coverage ≥ 70%. | CI gates |
| **NFR-7** | **Usability & a11y.** DaisyUI component consistency; all interactive elements ≥ 44 px; color contrast AA; focus-visible on everything; reduced-motion respected; screen-reader labels on inputs/charts (`aria-*`). | Playwright a11y pass + manual spot checks |
| **NFR-8** | **Documentation integrity.** After each iteration, [04](04-progress.md), [05](05-defects.md), [06](06-gap-analysis.md) are updated and [07](07-iterative-prompts.md) is regenerated — the workflow in [07](07-iterative-prompts.md). | Iteration checklist |
| **NFR-9** | **Time handling.** All times UTC in storage; dates are calendar dates (no TZ drift in day-boundary reports; DST-immune month/quarter boundaries — property-tested around DST transitions). | Unit property tests |
| **NFR-10** | **Money & quantity integrity.** Integer cents and scaled integers (§ AC-I1c) everywhere; a lint/property test forbids `float` in money/quantity arithmetic paths. | Static grep + property tests |
| **NFR-11** | **Portability.** Runs on Linux/windows/macOS dev environments with pinned versions (`pyproject`/`package-lock`); ports configurable; SQLite WAL mode enabled; no OS-specific features in v1. | Matrix smoke run |

## 12. Post-ITER-16 UX/platform enhancements (scheduled extensions)

These requirements are promoted from backlog items FEAT-003/004/005 and scheduled as post-core
iterations (ITER-17..ITER-19).

### FR-X1 — Theme preset (winter baseline)

The app shell defaults to DaisyUI **winter** theme while preserving accessibility and keeping user/business
semantics unchanged.

- **AC-X1a** — Given no user theme override exists, When an authenticated page loads, Then the shell theme resolves to `winter`.
- **AC-X1b** — Given keyboard-only navigation, When theme is applied, Then focus-visible, contrast, and hit-target behaviors remain compliant with NFR-7 on high-traffic screens.
- **AC-X1c** — Given existing pages, When the winter preset is enabled, Then no route behavior, auth guard, or ledger interaction changes.

### FR-X2 — Data table standardization

List/manage screens use one standardized open-source table foundation with shared interaction behavior.

- **AC-X2a** — A research decision record selects the table component against explicit criteria (accessibility, keyboard behavior, performance, licensing, maintenance, stack fit).
- **AC-X2b** — Users, Transactions, and Accounts screens migrate to the shared table wrapper with consistent sorting/filtering/paging and row-action affordances.
- **AC-X2c** — Large-list interaction remains within NFR-4 expectations and does not regress keyboard or screen-reader behavior (NFR-7).
- **AC-X2d** — Migration is staged (no big-bang): each converted screen ships with L3 regression tests and at least one L4 reachability check.

### FR-X3 — Navbar information architecture redesign

Navigation is restructured around a navbar parent with grouped submenus and route-backed submenu items.

- **AC-X3a** — Top-level structure is exactly: **Dashboard · Accounts · Investments · Reporting · Settings**.
- **AC-X3b** — Accounts submenu contains **Chart of Accounts, Categories, Transactions**; Investments submenu contains **Portfolio Research, Analysis**; Settings submenu contains **Profile, Posting, Seed Management, Backup and Download, Users, Audit**.
- **AC-X3c** — Every submenu item resolves to at least one reachable page (existing page or explicit placeholder), with no dead links.
- **AC-X3d** — Active-route highlighting and submenu keyboard controls satisfy FR-N/NFR-7 behavior.

### FR-X4 — Horizontal navbar IA refinement

Navigation is refined to use a **horizontal** top-level navbar while preserving route/auth ownership and
the shell interaction model.

> **Refinement note (ADR-007, 2026-11-10):** where FR-X3b and FR-X4b label the same submenus
> differently, the **FR-X4 wording governs** — Investments submenu = *Portfolio, Analysis, Research*
> and Settings submenu = *Backup and Downloads*. FR-X3 keeps its original wording as the superseded
> draft; route bindings and auth gating are unchanged.

- **AC-X4a** — Top-level horizontal order is exactly: **Dashboard · Accounts · Investments · Reporting · Settings**.
- **AC-X4b** — Accounts submenu contains **Chart of Accounts, Categories, Transactions**; Investments submenu contains **Portfolio, Analysis, Research**; Settings submenu contains **Profile, Posting, Seed Management, Backup and Downloads, Users, Audit**.
- **AC-X4c** — Every submenu item resolves to at least one reachable page (existing page or explicit placeholder), and route aliases remain consistent with shell contracts.
- **AC-X4d** — Active-route highlighting plus keyboard/screen-reader submenu behavior satisfy FR-N and NFR-7 without changing auth-gating or ledger/provider semantics.

### FR-IMP-1 — Portfolio CSV import (promoted from FEAT-001 backlog §3C, scheduled ITER-22)

Importing **portfolio positions** and **portfolio trade transactions** (buy/sell/dividend/fee rows) from
UTF-8 CSV into brokerage accounts, with a dry-run preview and atomic, all-or-nothing commitment (Q&A
resolutions in [08 §3C.7](08-backlog.md) are binding; the price-history stretch is AC-IMP1h). UI lands at
`/investments/import` (Portfolio tab) and is wired into the Investments submenu without changing existing
route aliases or auth gating.

- **AC-IMP1a** — *Mapping & account binding.* Column mapping happens in a wizard with saveable mapping templates (starters: *positions snapshot*, *trade history*, *bank statement*); every CSV account value maps explicitly to an existing InvestFlow **brokerage** account (create affordance gated on FR-C rules); accounts are never silently auto-created.
- **AC-IMP1b** — *Dry-run preview.* Every import first produces a preview: parsed rows, would-post transaction legs and amounts, the duplicate-skip report, positions-import "absent holdings" flags, and a total cash-movement sanity check; nothing posts until explicit confirmation.
- **AC-IMP1c** — *Atomicity & dedupe.* Each import is a single transaction: any hard row error aborts the whole file (no partial import); duplicates are soft-skipped — trades by hash-tuple `(date, ticker, type, qty, price, fee, cash-account)` matched against existing postings, positions by `(account, ticker)` replacement semantics — and both are listed in the applied report.
- **AC-IMP1d** — *Positions import* sets quantity + average cost directly (overwriting the account's existing **open** positions per `(account, ticker)`, flagged absent holdings confirmed at preview; closed positions keep realized P&L; a warning notes the average-cost-lots semantics) without posting synthetic buy transactions.
- **AC-IMP1e** — *Transactions import* posts through the **existing posting service** only (never writes `transaction_lines` directly; ledger invariants T-1 hold); dividend/fee rows are supported; replay order is enforced per `(account, ticker)` and out-of-order sell-before-buy rows are rejected with row errors, not auto-fixed.
- **AC-IMP1f** — *Limits.* Synchronous processing only; files ≤ 5 MB and ≤ 5,000 rows; larger inputs are refused at upload with a split-file suggestion; no background-job infrastructure (Q-4).
- **AC-IMP1g** — *Audit & reporting.* Each import records `audit_log` entries `import.positions` / `import.transactions` (entity = import batch id, row counts) and afterwards dashboards/reports reflect the imported state via the existing reporting engine.
- **AC-IMP1h** — *(Stretch; may slip to ITER-23)* *Price-history import* feeds `price_cache` with `source='manual'` from a daily close/volume CSV, subject to the AC-I2c manual-price precedence rules.

> **ITER-22 refinement (ADR-008, applied):** AC-IMP1e buy/sell rows update **positions only** through the
> avg-cost engine — no ledger legs (per D-08 positions live inside brokerage accounts, so trade cash flows
> belong to the mapped brokerage account; this keeps net-worth double-count-free). Dividend/fee rows post
> real balanced two-leg transactions through the posting service (cash leg + seeded `Interest & Dividends`
> / `Fees` COA leaf), with the dedupe hash stored as transaction `reference` `import:<hash16>` and in the
> `import_rows` registry. Dedupe matching is against the committed `import_rows` hash registry
> (equivalent to the AC-IMP1c hash-tuple over normalized fields). **AC-IMP1h slipped to ITER-23 as
> pre-agreed** — ITER-22 closed green without it; its starter template (`bank statement`) already ships.

> **ITER-23 refinement (ADR-009, applied):** AC-IMP1h landed — the *bank statement* starter template is
> repointed to the price-history shape (`Date/Ticker/Close/Volume`; its ITER-22 bank-statement-shaped
> columns were invalid for the `price_history` kind). Price rows are not account-bound; the commit upserts
> `price_cache` on the unique `(ticker, date)` key with `source='manual'` (never duplicate rows) and
> refreshes `latest_quotes` with the newest imported close per ticker (`asof` = the close date at midnight
> UTC, so the AC-I2b stale badge shows the true price date). Dedupe uses a price-row hash registry
> `(date, ticker, close_q4, volume)`: identical re-imports are duplicate-skipped; a corrected close for an
> existing `(ticker, date)` re-posts and upserts. Price history writes **no ledger rows** (02 §4.5);
> AC-I2c manual precedence holds (manual `latest_quotes` rows are served before staleness checks and
> provider rows do not overwrite them while they are current). FR-IMP-1 is now complete.

## 13. Data model summary

Detailed field tables live in [02-architecture](02-architecture.md) §3. Entity list:

`users · accounts · account_sensitive (encrypted fields, 1:1 with accounts) · categories · transactions · transaction_lines · positions (avg-cost, per account+ticker) · price_cache · import_mappings / import_batches / import_rows (import staging, ADR-008) · settings · audit_log · alembic_version`

## 14. Requirements-to-scope cross-check

| Original ask | Covered by | Notes |
|---|---|---|
| FastAPI backend, Next.js/TS/DaisyUI/Tailwind | NFR-1, D-16 | — |
| SQLite database | D-11, 02 §3 | WAL mode |
| Top mega menu | FR-N | — |
| Account info encrypted at rest | FR-E | — |
| Accounts management (COA, categories) | FR-C, FR-K | — |
| Simple transaction mgmt (credits/debits) | FR-T | Under strict double-entry invariants (D-04) |
| Investment mgmt (analysis, TA, info, news, portfolio, graphs, optimization) | FR-I | Yahoo provider D-10 |
| User mgmt (username, password, active/inactive) | FR-U | Single role D-03 |
| Robust reporting (COA, budget, cash flow, monthly, quarterly, summary, Excel/PDF) | FR-R | **Budget dropped** per D-06 → recording kept here for trace |
| Focus on cash flow & net worth | FR-D, FR-R5/R6 | — |
| Home dashboard w/ drill-down | FR-D | — |
| Login screen | FR-U2 | — |
| Registration screen | FR-U1 | — |
| Settings screen | FR-S | Recommended + admin extras (D-12) |
