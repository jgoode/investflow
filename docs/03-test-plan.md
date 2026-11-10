# InvestFlow — 03 · Test Plan

| | |
|---|---|
| **Status** | Active |
| **Last updated** | 2026-11-08 |
| **Parents** | [01-requirements](01-requirements.md) (AC ids) · [02-architecture](02-architecture.md) |
| **Process** | Strict TDD — every requirement is implemented **failing-test-first** within its iteration (D-15) |

## 1. Goal and principles

1. **Tests before code.** Each iteration starts by translating its AC items (from [01](01-requirements.md) + [00 §4](00-overview.md)) into red tests; those tests (unit → integration → E2E) are the iteration's definition-of-done.
2. **Traceability.** Every AC id maps to at least one test case (§4 matrix). An untested AC is a defect in [05-defects](05-defects.md).
3. **Test pyramid.** Many fast unit tests, fewer service/API integration tests, thin E2E happy-path suites per iteration.
4. **No floats in money/quantity logic** (NFR-10): lint + property tests guard integer arithmetic and cents-only boundaries.
5. **Crypto is test-obsessed** (FR-E ≥ 95% branch coverage, all failure paths tested).

## 2. Layers, tooling, layout

| Layer | Tool | Where | Scope | Speed target |
|---|---|---|---|---|
| L1 Unit | pytest (+ property tests via `hypothesis`) | `backend/tests/unit/**` | pure services: `money`, `avg_cost`, `ta`, `mvo`, `reporting_engine` math, crypto unit, formatters | < 5 s total |
| L2 API/Integration | pytest + `httpx.AsyncClient` against FastAPI with per-test **temporary SQLite file** + fixtures (`fresh_db`, `seeded_coa`, `demo_book`, `pinned_clock`). Single-process. | `backend/tests/api/**` | router+service+DB behavior, auth/session/cookie flows, encryption storage bytes, error contracts, provider **mocked at httpx transport level** | < 60 s |
| L3 Frontend unit/component | vitest 3 + React Testing Library + `msw` | `frontend/**/__tests__/**` | component logic, React Query hooks vs msw, zod schema parity, a11y of critical widgets | < 30 s |
| L4 E2E | Playwright (chromium + webkit spot runs) | `e2e/**` | whole-app journeys on real UI, with **`mockProviderRoutes`** (playwright route interception) for Yahoo + seeded temp backend | < 3 min |

Shared util: `tests/utils.py` (seed books, GWT builders, money/qty helpers, fake clock `time_machine`).
E2E always runs against the **stacked real build** (real backend + real frontend on :8000/:3000), never against mocks of our own backend.

## 3. Iteration-level TDD loop (matches [07-iterative-prompts](07-iterative-prompts.md) §3)

```
  1 SELECT ACs for iteration (from 01 + progress doc status)
  2 WRITE RED tests: L1/L2 for backend slice, L3/L4 for UI slice
  3 RUN make test → confirm failures are for the right reasons (test quality gate)
  4 IMPLEMENT minimal code (backend slice / frontend slice)
  5 GREEN: make test && make test-e2e (this iteration's scenarios only)
  6 REFACTOR: lint (ruff/mypy/eslint/tsc), coverage check vs NFR-6 targets
  7 UPDATE docs roll-forward (04, 05, 06, 07 — workflow in 07)
  8 Beat bugs → 05-defects entries (never delete failing tests to go green)
```

## 4. Traceability matrix (AC → test layer → iteration)

Legend: `U`=L1, `I`=L2, `C`=L3, `E`=L4. `•` = primary home for that AC's test; others supporting.

| AC | U | I | C | E | Iter | Primary test sketch |
|---|---|---|---|---|---|---|
| U1a–U1d registration | • | • |  |  | 2 | API POST /auth/register dup/weak; I-tier duplicate ID pass |
| U2a–U2d login / throttling / inactive | | • | | • | 2 | timing-equal error + lockout counter; E: login flow |
| U3a–U3b logout/401 | | • | | • | 2 | cookie clear; API 401 → /login |
| U4a–U4e user mgmt | | • | | • | 3 | deactivate bumps epoch; last-active refused |
| C1 seed COA idempotent | • | • | | | 5 | migration test + re-seed count |
| C2–C6 CRUD, tree, archive, balance, placeholder | • | • | | • | 5 | cycle trigger; recompute balances test (C5) |
| K1–K4 categories | • | • | | • | 6,15? | delete→(uncategorized); rename propagation |
| T1–T3 quick/advanced posting + imbalance | • | • | | • | 7 | PostImbalance 422; E: quick-post happy path |
| T4 transfer | • | • | | | 8 | two-line transfer; balances updated |
| T5 list & filter | • | • | | | 7,8 | filter/URL params; paging; running balance (T8) |
| T6–T7 edit/void | • | • | | | 8 | void excluded from reports; audit entries |
| T9, T10 | • | • | | • | 7,8 | masked dropdowns (E: visual); memo plaintext scope |
| I1a–I1d avg cost, buy/sell, precision, oversell | • | • | | | 12 | buy/sell math property tests; API oversell 409→422 |
| I2a–I2d provider cache & fallback & discipline | • | • | • | | 13 | cache 15 min; down-provider degradation; manual precedence |
| I3a positions grouping | • | • | | • | 12,15? | grouped page; sort per spec |
| I4a–I4b news | | • | | | 14 | news adapter mocked; empty/error state |
| I5a–I5c TA indicators | • | • | | | 14 | fixture validation ≤1e-6; insufficient-data path |
| I6a–I6c portfolio analysis metrics | • | • | | | 15 | Sharpe/drawdown/beta fixtures; graph data endpoint |
| I7a–I7d optimization | • | • | | • | 15 | MVO optimum known-answer tests; AC-I7c short-history branch |
| R1–R10 reports/export | • | • | | • | 9,10 | derived-vs-raw ledger equal; xlsx/pdf cross-check per §5.3 |
| D1–D5 dashboard | | • | • | • | 11 | ≤ 2 batched calls (AC-D3); drill deep links |
| S1–S8 settings | • | • | | • | 16 | provider key masked; seed merge; backup byte-consistent |
| E1–E8 encryption | • | • | | | 4 (~16 diag) | §5.2 dedicated suite |
| N1–N4 mega menu | | | • | • | 2,5,11 | keyboard nav test; route highlight |
| NFR-2 auth on all paths | | • | | • | 2+ | guard matrix: every protected route returns 401 unauthed |
| NFR-3 security suite | | • | | | ongoing | §5.4 |
| NFR-4 perf budget | | • | | | 10,16 | §5.5 benchmarks |
| NFR-5 reliability | • | • | | | ongoing | transaction rollback/unwritable-provider chaos |
| NFR-9 DST/date property | • | | | | 9 | month/quarter boundaries across DST |
| NFR-10 money/int guards | • | | | | 4+ | grep-lint + hypothesis cents rounding |

*(iterations referencing "15?" resolve in [04-progress](04-progress.md) roadmap — see §6 mapping table there.)

*ITER-01 close note: skeleton iteration — no AC matrix rows yet. `/api/healthz` is covered at L2
(`backend/tests/api/test_healthz.py`) and by the L4 smoke (`e2e/smoke.spec.ts`); NFR-11 SQLite conventions
at L1 (`backend/tests/unit/test_db_connection.py`). The healthz smoke doubles as the NFR-2 exempt-path
check from ITER-02 onward.*

*ITER-02 close note: U1/U2/U3/N partial rows are now covered at their mapped layers — backend L2 auth/session
suite (`backend/tests/api/test_register.py`, `backend/tests/api/test_login.py`, `backend/tests/api/test_auth_session.py`),
frontend L3 validations/menu shell (`frontend/app/__tests__/pages.test.tsx`, `frontend/app/__tests__/mega-menu.test.tsx`),
and L4 journey (`e2e/smoke.spec.ts`: register → dashboard → logout → login).*

*ITER-03 close note: U4 row is now covered at mapped layers — backend L2 user-management suite
(`backend/tests/api/test_users.py`) verifies list/edit/activate-deactivate/delete guard/password refresh behaviors;
frontend L3 keeps Users navigation enabled/regression-tested (`frontend/app/__tests__/mega-menu.test.tsx`);
L4 scenario extends through `/users` with own-password change and re-login (`e2e/smoke.spec.ts`).*

*ITER-04 close note: E1–E8 rows are now covered at mapped layers — backend crypto contract suite
(`backend/tests/unit/test_crypto_battery.py` + `backend/tests/unit/test_account_sensitive_contract.py`) checks
DB byte-scan and WAL-safety, AAD mismatch, wrong-key behavior, masking/log-safety, and rotation idempotence;
all E2E smoke and standard `make test`/`make lint`/`make test-e2e` gates remain green.*

*ITER-09 close note: R1–R4/R9/R10 report-core slice is now covered at mapped layers — backend L2 report API suite
(`backend/tests/api/test_reports.py`) verifies COA/summary/monthly/quarterly outputs, date-range filtering,
void-default exclusion with explicit toggle inclusion, URL-ready normalized parameters, and the historical-integrity
comparison against raw `transaction_lines`; backend L1 report-engine coverage (`backend/tests/unit/test_reports_engine.py`)
pins deterministic server-side aggregation behavior, and L4 smoke adds a shareable reports-URL scenario
(`e2e/smoke.spec.ts`) that reloads with the same params and asserts identical period output.*

*ITER-10 close note: R5–R8 report-export slice is now covered at mapped layers — backend L2 report API suite
(`backend/tests/api/test_reports.py`) verifies cash-flow and net-worth totals, filtered date ranges, and XLSX/PDF
export names/content parity with the API payloads; backend L1 report-engine coverage (`backend/tests/unit/test_reports_engine.py`)
pins deterministic ledger-plus-position valuation behavior, and the repo-wide `make test`/`make test-e2e`/`make lint`
set remains green for the iteration close. *

*ITER-15 close note: I6a–I6d and I7a–I7d rows are now covered at mapped layers — backend L2 portfolio suite
(`backend/tests/api/test_portfolio.py`) verifies the portfolio summary contract, weighted-return contributions,
constraint feasibility, insufficient-history handling, and advisory-only optimization output; the repo-wide
`make test`/`make test-e2e` and lint/type gates remain green for the iteration close.*

*ITER-07 close note: T1–T3/T5/T9 rows are now covered at mapped layers — backend L2 transaction suite
(`backend/tests/api/test_transactions.py`) verifies quick income/expense posting, split-line balancing,
imbalance rejection, list/filter paging, and account-number masking without altering encrypted sensitive-field
boundaries; frontend L3 regression coverage remains green (`frontend/app/__tests__/mega-menu.test.tsx`), and
L4 smoke still passes in lockstep with the crypto/AAD battery.*

*ITER-06 close note: K1–K4 row is now covered at mapped layers — backend L2 category suite
(`backend/tests/api/test_categories.py`) verifies seeded starter categories are idempotent, flow↔default-account
constraints hold, line assignment plumbing works, and category delete re-points historical line references to
`NULL` (reported as "(uncategorized)"); frontend L3 menu regression (`frontend/app/__tests__/mega-menu.test.tsx`)
includes Categories navigation; L4 scenario (`e2e/smoke.spec.ts`) covers category create/delete via the minimal
category screen while preserving the crypto regression battery in parallel backend runs.*

## 5. Dedicated suites

### 5.1 Auth/session suite (Iterations 2–3)

Per-cookie matrix tests: unauthenticated hit on every protected `/api/**` + route → 401/redirect.
Authentication chain tests: register → login → me → deactivate-across-sessions → epoch → re-login.
Generic-msg + timing-equal failure test (assert response-time delta between valid-user/wrong-password
and unknown-user paths stays within a 2× fudge factor under load noise). Account-threshold throttle counter
test resets after cooldown (faked clock).

### 5.2 Encryption suite (Iteration 4, maintained forever — FR-E) — the "crypto battery"

1. **E1**: insert an account with `account_number="1234-5678-9012-3456"` into an existing real DB → open file, scan
   every byte: no plaintext occurrence (also para: never stored in WAL). Then restart app with same key → decrypt OK (E3).
2. **AAD binding (E2)**: copy ciphertext BLOB of account A's `account_number_enc` into account B → rest reads decrypt-error / masked,
   cross-prefix audit count exactly 1 per field mismatch attempt.
3. **Key-missing behaviour (E3/E5)**: wrong/lost key file → reads return masked/plaintext-free non-crash, diagnostics count-up
   (AC-E8 shows `2 encrypted, 0 errors`).
4. **Rotation (E4)**: seed v1 → write 3 accounts → rotate v2 → all decrypt, DB has zero v1 key_id rows after backfill,
   rotation idempotent, old key removed from active keyring config no longer breaks reads (`loader reads all versions`).
5. **Log safety (E5)**: induce decrypt fault; capture logs; assert ciphertext-safe.
6. **Masking (E6)**: reveal/end-to-end UI test: reveal once → clears on route-exit / per-event; clipboard confirm per event.
7. **Export masking (E7)**: generate xlsx + pdf twice — default (masked) and confirmed (readable); assert sheet content.
8. **Codec unit**: GCM nonce uniqueness stress (10k encrypts same plaintext → ≥99.9% unique payloads),
   tampered-byte detection, integer `key_id_len` unterflow prevention.

### 5.3 Report/export cross-check suite (Iterations 9–10)

- Insert curated book data (12 months transactions incl. voids, transfers, categories, fees).
- Assert each report equals a **second implementation** (brute-force Python from raw lines) for
  COA/summary/monthly/quarterly/cash-flow/net-worth (AC-R10).
- Export tests: unzip xlsx → check header freeze, cell values; PDF → extract text (pdfminer stub fixture),
  compare numeric tokens to table data within 2-decimal rounding.
- Monthly+quarterly month-boundary + DST property tests (NFR-9), translated to local time zone overlays.

### 5.4 Security suite (aligns NFR-3)

- CSRF: mutating fetch without `X-Requested-With` → 403.
- Cookie flags: `Set-Cookie` contains `HttpOnly`, `SameSite=Lax`, `Secure` (when not dev).
- No plaintext secrets in logs (grep-coded tests, §5.2.5).
- Login-lockout pacing test per AC-U2c; account enumeration not possible via API response shapes.

### 5.5 Performance suite (slack-mode, iterations 10 & 16 bench-repin)

- Generate seeded book: 50k lines / 3 years / 6 accounts / 12 tickers daily prices.
- Targets from NFR-4 measured in pytest: dash batch P95 < 500 ms, reports P95 < 2 s, list-page < 300 ms.

## 6. Coverage targets (NFR-6)

- Backend ≥ 85% lines; `crypto/`, `money/`, `services/{avg_cost,portfolio}` ≥ 95%.
- Frontend ≥ 70% (vitest c8 coverage; generated chart-library adapter shims excluded from targets).
- E2E: ≥ 1 scenario per iteration + the suites §5.1, §5.3 polish set.

## 7. Mocks, fixtures, and seeded data

- **Yahoo provider**: L2 intercepts at httpx transport; L4 mocks via Playwright `page.route` (never real network
  in tests — D-10); cache tests assert expiry windows and manual-override precedence.
- **DB**: fixture `book` = fresh seeded COA + 1 demo user; `book_w_txns` adds deterministic transactions from YAML
  scripts, covering all report shapes.
- **Crypto keys**: temp keyring file per test session, unique key or ID per test module.
- **Clock**: `time-machine` pinned to fixed UTC dates to make month boundaries deterministic (NFR-9).
- **No live secrets in CI**: keys generated per CI job (GitHub Actions-friendly pattern documented in 02 §7).

## 8. Failure-handling rules for the dev loop

1. Failing test tracking: tests must document **why they failed initially** (expected error snapshot) — commit both test + fail-log in iteration PR.
2. A test can be changed **only** via right-failures-are-bugs rule ([05-defects](05-defects.md)) D-ref,
   never deleted because "flaky" — it's fixed or upstream-root-caused.
3. Any bug found during iteration gets a [05-defects](05-defects.md) entry before hotfix; regression test is
   added at the layer where it slipped through and is kept forever.
