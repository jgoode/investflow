# InvestFlow — 04 · Progress

| | |
|---|---|
| **Status** | Rolling document — update at the end of **every** iteration (workflow: [07-iterative-prompts](07-iterative-prompts.md) §2) |
| **Last updated** | 2026-11-09 (ITER-11 ✅ closed) |

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
| **ITER-12** | Investment accounts & positions | Brokerage accounts, buy/sell flows, avg-cost engine + property tests, position list grouped, position CRUD (manual only) | FR-I1, FR-I3 (manual part) | 📋 | — |
| **ITER-13** | Market data adapter | Yahoo adapter (quote/history/profile), price_cache + latest_quotes + 15-min freshness, manual fallback screen/precedence, stale badges, rate-limit discipline | FR-I2 (+ AC-I3a finalize) | 📋 | — |
| **ITER-14** | Position detail + news + TA | Position screen (info, sparkline), news fetch+cache, baseline indicators + lightweight-charts graphs, fixture validation, insufficient-data handling | FR-I3, FR-I4, FR-I5 | 📋 | — |
| **ITER-15** | Portfolio analysis + optimization | Portfolio page (weights, allocation, return timeline graphs), risk metrics, MVO frontier/max-Sharpe/min-var, constraint fields, disclaimer | FR-I6, FR-I7 | 📋 | — |
| **ITER-16** | Settings & polish | Settings tabs (profile/currency/provider/posting defaults/seed mgmt/backup/audit viewer), a11y + styling pass, full test-suite + benchmark re-run, README quickstart | FR-S, NFR-7, NFR-4 re-bench | 📋 | — |

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

(served as "expected bootstrap" so sessions know exactly which docs the next iteration touches;
update real rows on finish.)
