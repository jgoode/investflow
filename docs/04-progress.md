# InvestFlow — 04 · Progress

| | |
|---|---|
| **Status** | Rolling document — update at the end of **every** iteration (workflow: [07-iterative-prompts](07-iterative-prompts.md) §2) |
| **Last updated** | 2026-11-08 (ITER-01 ✅ closed) |

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
| **ITER-02** | Auth core | Registration screen/screen-level validation, login + JWT httpOnly cookie + logout, auth-gated app layout, mega menu partial (menu groups Dashboard/Reports throttle later), login-throttle, Users table | FR-U1, FR-U2, FR-U3, NFR-2, FR-N | 📋 | — |
| **ITER-03** | User management | Users list/edit screens, activate/inactive with session revocation (epoch), own-password change, last-active guard | FR-U4 | 📋 | — |
| **ITER-04** | Encryption core + crypto battery | `crypto/` AES-256-GCM service, key store/gen, AAD, masking helper, rotation job, DB-scan test suite | FR-E (E1–E8), NFR-3 | 📋 | — |
| **ITER-05** | Chart of accounts | Models+migrations, seed COA v1 (idempotent), COA tree UI, account CRUD+archive, encrypted detail fields wired end-to-end (sensitive screen) | FR-C, FR-N full menu, D-16 seed | 📋 | — |
| **ITER-06** | Categories | Category CRUD, starter categories, assignment plumbing, defaults | FR-K | 📋 | — |
| **ITER-07** | Simple transactions | Posting service + invariants, expense/income quick post UI, split-lines editor with off-by balance lock, list with filters/paging | FR-T1–T3, T5, T9 | 📋 | — |
| **ITER-08** | Transfers, edit, void, audit | Transfer flow, edit-full-replace, void flow + confirmation, running balance, audit_log wiring | FR-T4, T6–T8, T10 | 📋 | — |
| **ITER-09** | Reports core | Reporting engine interface, COA report, summary, monthly, quarterly; date filters/void exclusion | FR-R1–R4, R9, R10, NFR-9 | 📋 | — |
| **ITER-10** | Cash flow, net worth, exports | Cash-flow report, net-worth statement (+holdings valuation join), export xlsx + pdf, perf benchmarks baseline | FR-R5–R8, NFR-4 | 📋 | — |
| **ITER-11** | Dashboard | Dashboard cards, Recharts graphs (net worth trend, in/out bars), drill-down deep links, onboarding empty states, card layout prefs | FR-D, AC-D–…D5, FR-N menus final | 📋 | — |
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
