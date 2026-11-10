# InvestFlow — 02 · Architecture

| | |
|---|---|
| **Status** | Active |
| **Last updated** | 2026-11-10 (post-ITER-16 extension planning applied) |
| **Parent** | [00-overview](00-overview.md) · Decisions D-01…D-16 |

## 1. System overview

```
┌──────────────────────────────────────────────────────────────────┐
│  Browser (localhost:3000)                                        │
│  Next.js 15 App Router · React 19 · TypeScript ·                 │
│  Tailwind 4 + DaisyUI 5 · Recharts · lightweight-charts          │
└──────────────┬───────────────────────────────────────────────────┘
               │ /api/** (JSON, JWT httpOnly cookie)
┌──────────────▼───────────────────────────────────────────────────┐
│  Backend — FastAPI (Python 3.11), uvicorn, localhost:8000         │
│  ├─ routers/            (auth, users, accounts, categories,      │
│  │                       transactions, reports, investments,     │
│  │                       market, portfolio, settings, audit,     │
│  │                       export)                                 │
│  ├─ services/           (ledger, avg_cost, valuation, ta,        │
│  │                       mvo, reporting_engine, exporter,        │
│  │                       crypto, audit, backup)                  │
│  ├─ providers/          (MarketDataProvider ABC + YahooFinance   │
│  │                       adapter + offline/manual adapter)       │
│  ├─ money/  crypto/     (int-cents math, AES-256-GCM field enc)  │
│  └─ db/                 (SQLAlchemy 2.0 models, Alembic, seed)   │
└──────────────┬───────────────────────────────────┬───────────────┘
               │                                   │
     ┌─────────▼─────────┐                ┌────────▼─────────────┐
     │ SQLite (WAL)      │                │ Yahoo Finance        │
     │ investflow.db     │                │ unofficial endpoints │
     │ (plain file,      │                │ (cached in           │
     │  frags encrypted  │                │  price_cache)        │
     │  at field level)  │                └──────────────────────┘
     └───────────────────┘
```

Run model: two processes started together via `make dev` / `pnpm dev:all`; backend on :8000
(CORS: allow http://localhost:3000 only), frontend proxying nothing (direct fetch with cookie).

## 2. Technology stack (locked, D-16)

| Layer | Choice | Version (min) | Rationale / notes |
|---|---|---|---|
| OS/runtime | Python | 3.11+ | stdlib `sqlite3` thread mode, typing |
| Web framework | FastAPI + uvicorn | 0.111+ | typed routers, pydantic v2 DTOs |
| ORM / migrations | SQLAlchemy 2.0 + Alembic | 2.0.30+ / 1.13+ | typed models, migration history |
| DB | SQLite (WAL, `foreign_keys=ON`) | 3.40+ | single-file, backup-able |
| Password | argon2-cffi | 23+ | argon2id, memory-hard |
| Auth token | PyJWT (HS256) + httpOnly cookie | 2.8+ | 12 h expiry, server revocation via `users.session_epoch` counter (see §4.3) |
| HTTP client (provider) | httpx | 0.27+ | timeouts, retries at adapter level |
| Crypto | `cryptography` AESGCM | 42+ | AES-256-GCM with AAD |
| Money | integer cents (`int`) | — | NFR-10; no floats |
| Excel export | xlsxwriter | 3.2+ | styled, streaming write |
| PDF export | WeasyPrint | 62+ | HTML→PDF, headers/footers/page numbers |
| TA math | numpy + pandas (fixture-validated) | 1.26/2.2 | indicator tests vs reference fixtures |
| Optimizer | numpy `linalg`, scipy.optimize for frontier solve | 1.34/1.13 | no heavy ML deps |
| Frontend framework | Next.js (App Router) | 15+ | server components for gates, client components for interactivity |
| React | React | 19+ | pairs with Next 15 |
| Styling | Tailwind CSS + DaisyUI | 4.x / 5.x | utility classes + preset components |
| Charts | Recharts (dashboard/reports), lightweight-charts v4 (position TA) | — | two-chart strategy: declarative + financial |
| State | React Query `@tanstack/react-query` v5 | — | server-state cache, invalidation on mutation |
| Forms | React Hook Form + zod v4 | — | shared zod schemas mirrored in pydantic |
| Tests (backend) | pytest + pytest-asyncio + httpx | — | FastAPI TestClient |
| Tests (frontend) | vitest 3 + React Testing Library | — | unit/component |
| Tests (E2E) | Playwright | — | `mockProviderRoutes` for market data |
| Lint/format | ruff + mypy (strict), eslint flat + tsc --noEmit | — | CI gates (NFR-6) |

Monorepo layout:

```
investflow/
├─ backend/         (FastAPI app, package name `app`)
├─ frontend/        (Next.js app)
├─ e2e/             (Playwright L4 suite — docs/03-test-plan.md §2; ADR-005)
├─ docs/            (this documentation set)
├─ package.json     (root — home of the Playwright test runner; ADR-005)
├─ Makefile         (setup, dev, test, lint, migrate, test-e2e; later adds dev-all, seed, test-all, backup per §7)
└─ README.md
```

## 3. Data model (SQLite)

Conventions: `id` INTEGER PK, `created_at`/`updated_at` UTC unixepoch INTEGER, money `*_cents` INTEGER,
quantities/prices `*_q4` INTEGER (×10⁴). All Fks with `ON DELETE` per column; `PRAGMA foreign_keys=ON`, WAL.

### 3.1 Tables

**users**

| column | type | notes |
|---|---|---|
| id | INTEGER PK | |
| username | TEXT UNIQUE | lowercased at write |
| display_name | TEXT NULL | |
| password_hash | TEXT | argon2id |
| is_active | INTEGER | 0/1 |
| session_epoch | INTEGER | incremented to invalidate all sessions (AC-U4b) |
| created_at / updated_at | INTEGER | |

**accounts**

| column | type | notes |
|---|---|---|
| id | INTEGER PK | |
| code | TEXT UNIQUE | user-maintained |
| name | TEXT | |
| type | TEXT CHECK | `asset\|liability\|income\|expense\|equity` |
| subtype | TEXT CHECK | `group\|bank\|cash\|brokerage\|credit_card\|fund\|other` |
| parent_id | INTEGER FK→accounts | NULL for the 5 type roots (seeded) |
| institution | TEXT NULL | |
| description | TEXT NULL | |
| last4 | TEXT NULL | derived at write from plaintext (AC-E6) |
| is_archived | INTEGER | |
| is_investment | INTEGER | subtype in `brokerage,fund` |
| created_at / updated_at | INTEGER | |
| *checks* | | no cycles (trigger), root type = branch type (AC-C3) |

**account_sensitive** (1:1 with accounts, all ciphertext; *never read by reports*)

| column | type | notes |
|---|---|---|
| account_id | INTEGER PK FK→accounts ON DELETE CASCADE | |
| account_number_enc | BLOB NULL | AES-GCM payload (§6) |
| routing_transit_enc | BLOB NULL | |
| transfer_numbers_enc | BLOB NULL | e.g., IBAN/wire refs |
| notes_enc | BLOB NULL | any free-form secret |
| key_id | TEXT | active cipher key version |

**categories**

| column | type | notes |
|---|---|---|
| id INTEGER PK / name TEXT UNIQUE / flow | | `income\|expense` |
| color TEXT / default_account_id INTEGER FK→accounts NULL | | pre-select in TX form |
| created_at / updated_at | INTEGER | |

**transactions**

| column | type | notes |
|---|---|---|
| id INTEGER PK / date TEXT (ISO date) / description TEXT / reference TEXT NULL | | |
| status | TEXT CHECK | `posted\|void` |
| created_by INTEGER FK→users NULL / created_at / updated_at | | |

**transaction_lines**

| column | type | notes |
|---|---|---|
| id INTEGER PK / transaction_id FK / account_id FK→accounts | | |
| direction | TEXT CHECK | `debit\|credit` |
| amount_cents | INTEGER CHECK(amount_cents > 0) | magnitude; direction carries sign |
| memo TEXT NULL / category_id FK→categories NULL | | FR-K |
| *Index* | | `(date)` via join, `(account_id)`, `(category_id)`; covering idx `(id, transaction_id)` |

*Ledger invariant enforced by service layer + DB trigger:* Σ debit_cents = Σ credit_cents per transaction (T-1).

**positions** *(unique `(account_id, ticker)`)*

| column | type | notes |
|---|---|---|
| id PK / account_id FK / ticker TEXT (upper) | | |
| quantity_q4 INTEGER | | signed ≥ 0; negative not allowed (D-09) |
| avg_cost_q4 INTEGER | | average-cost method (AC-I1a/b) |
| status TEXT | | `open|closed` |
| realized_gain_loss_cents INTEGER | | cumulative realized P&L for the position lifecycle |
| updated_at / created_at | | |

**price_cache** *(unique `(ticker, date)`)*

| column | notes |
|---|---|
| id PK / ticker TEXT / date TEXT | daily close rows |
| close_q4 INTEGER / volume INTEGER / source TEXT | `yahoo\|manual` |
| fetched_at INTEGER | |

*Plus a `latest_quotes` small table* (`ticker` PK, `price_q4`, `asof`, `source`, `fetched_at`) for the 15-min freshness rule (AC-I2a).

**settings** *(typed KV; effects validated against enum table)*

| column | notes |
|---|---|
| key TEXT PK / value TEXT / value_type TEXT | `str\|int\|json` |
| scope TEXT DEFAULT 'global' | 'global' or 'user:<id>' |
| updated_at / updated_by FK→users NULL | audited |

Used keys (initial): `currency.label` (USD), `currency.symbol`, `locale.first_weekday`,
`posting.future_days` (0–30), `provider.selected` (`yahoo\|manual`), `provider.api_tokens` (JSON, sensitive —
stored encrypted through the same AES-GCM service) · user prefs: `dashboard.cards_order`.

**audit_log**

| column | notes |
|---|---|
| id PK / user_id FK→users NULL / action TEXT | e.g. `auth.login`, `tx.post`, `tx.void`, `settings.update`, `users.active`, `backup.export` |
| entity TEXT / entity_id INTEGER NULL | e.g. `accounts/42` |
| summary TEXT | **masked** per FR-E/AC-S7 — never contains decrypted secrets |
| created_at INTEGER | index `(created_at)` |

**seed_meta** (`name` PK, `version`, `applied_at`) — idempotent COA/category seeds (AC-C1, AC-S5).

### 3.2 Indexes & performance notes (NFR-4)

- `transaction_lines(account_id)` + `transactions(date)` composite idx on hot report path
- `positions(account_id)` + `positions(account_id, status)`
- `price_cache(ticker, date)` covering; `latest_quotes` tiny (OO)
- Report engine reads *aggregates* via SQL (`SUM` grouped), not row scans in Python for 50k-line scale.

### 3.3 Seed COA draft (v1)

```
Assets            (asset/group)
 ├─ Cash            (asset/cash)
 ├─ Bank Accounts ▸ e.g. "Bank A" (asset/bank)
 └─ Investments ▸   "Brokerage A" (asset/brokerage, is_investment=1)
Liabilities       (liability/group)
 ├─ Credit Cards ▸  "Credit Card A" (liability/credit_card)
 └─ Loans ▸         "Loan A" (liability/other)
Income            (income/group)
 ├─ Salary • Interest & Dividends • Realized Gains • Other Income
Expenses          (expense/group)
 ├─ Housing • Food • Transportation • Utilities • Healthcare
 ├─ Insurance • Entertainment • Travel • Education • Fees • Other
Equity            (equity/group)
 └─ Opening Balance (equity/other)   ← balances initial book value
```

Seed applies with version from `seed_meta`; re-apply merges *additions only* (AC-S5).

## 4. Backend design

### 4.1 Layering

```
routers (HTTP, pydantic DTOs) → services (domain logic, transactions) → db models
   ↑ money/, crypto/, providers/ used by services only
```

Rules: routers never touch the ORM directly; services own transactions (`async with session.begin()`);
domain errors → typed exceptions mapped by a single exception handler (422 validation, 401/403 auth, 404, 409 conflicts e.g. oversell, 429 throttles).

### 4.2 Identity & roles

All registered users are equal (D-03). Guards: `Depends(get_current_user)`; admin-extra pages (Settings §7)
require activity (any active user may use them — the "admin extras" naming only means capability lives there).

### 4.3 JWT/session mechanics (NFR-2)

- Token payload: `{sub: user_id, epoch: <users.session_epoch>, exp: 12h}`; HS256, key from `INVESTFLOW_JWT_SECRET`
  (env var; dev default auto-generated & written to a repo-ignored `.secret/jwt` with 0600, matching FR-E key pattern).
- Cookie `investflow_session`: httpOnly, SameSite=Lax, Secure (same-origin), Path=/.
- Revocation: verifying `epoch` matches `users.session_epoch` (bump on deactivate/last login reset) → AC-U4b.
- CSRF defense: SameSite=Lax + require header `X-Requested-With: investflow` on all mutating requests (NFR-3).

### 4.4 Field-level encryption (crypto/, FR-E)

Payload format (BLOB):

```
version(1B) | key_id_len(1B) | key_id(ASCII) | nonce(12B) | ciphertext+GCM_tag(16B)
AAD = b"a:{table_name}:{field}:{entity_id}"     (entity_id NOT in payload — DB identity)
```

- Key store: `crypto/keyring.py` loads sorted key-ids from env var `INVESTFLOW_ENC_KEYS` (JSON `{key_id: base64}`)
  **or** from `INVESTFLOW_ENC_KEY_FILE` (JSON, mode 0600). If neither: first boot generates `{"v1": …}` key file,
  logs a warning reminding the user to copy the key.
- Writes: `encrypt(table, field, entity_id, plaintext)` → BLOB; `active_key_id` global (current settings).
- Reads: try current key then all loaded keys (version-pin subscription); on no key decryptable → error type
  surfaced as masked `•••` (never plaintext, AC-E5), counted in diagnostics (AC-E8).
- Registry: crypto is **field-scoped**; a `ENCRYPTED_FIELDS` table-driven list (accounts §3.2 rows) is the
  single source of truth consumed by models, migration validators, audit masking, diagnostics, and test scans
  (AC-E1 DB scan test is data-driven from that list).
- Rotation (AC-E4/§7): CLI `make rotate-key NEW_ID=v2` → backfill job decrypts all registry fields with loaded v1,
  re-encrypts with v2, sets active key id, verifies counts equal, snapshot before/after diff, logs counts only.
- **What is NOT encrypted:** transaction memos (visible by design, AC-T10), Tickers/account names, balances.
  Tickers and account names stay in clear for report grouping.
- Password/last4 (`accounts.last4`) plaintext is allowed only from write-time derivation (AC-E6), never from ciphertext.

### 4.5 Ledger posting service

```
post_transaction(lines, date, description, ...):
   validate ∀ lines (amount>0, direction ∈ {debit, credit}, account open+leaf)
   Σ debits == Σ credits → else raise PostImbalance
   insert tx + lines atomically
```

Void: `status=void` (lines retained), reports filter by default (AC-T7). Edit = replace all lines,
linked `updated_at`, audit `tx.edit` (FR-T).

### 4.6 Investment services

- **avg_cost** (`services/avg_cost.py`): buy/sell math on scaled ints, always integer division rounded to the
  share's best interest at first-principles: avg_cost_q4 promotes correctly on fees (AC-I1a), P&L derives
  from pre-rounded average (property-tested, see [03-test-plan](03-test-plan.md) §4.2).
- **valuation**: `val = quantity × latest_quotes.price` (+ positions cash if debt-free explanation needed); simple,
  no templates; reads `is_manual` when fallback applies. Cash never double-counted (AC-R6).
- **ta** (`services/ta.py`): pandas/numpy indicator implementations, validated against reference fixtures;
  input = price_cache ascending dates, output = aligned series for lightweight-charts.

### 4.7 Portfolio optimization (mvo ~ service)

- Input: cached daily closes (≥120 days, else AC-I7c path), `rf` from settings (default 0.02).
- Compute daily returns → annualized (means, covariance ×252).
- Maxima: `scipy.optimize.minimize` with negative Sharpe & min-variance objectives, bounds/free config,
  simplex sum-to-1 constraint (long-only v1; shorts excluded per position model not needed).
- Frontier: scan Min-Var→Max-Ret ranges to ≥30 points. Outputs **weights + metrics only**; always UI disclaimer.

### 4.8 Reports engine

Single interface: `run_report(kind, params, session) -> ReportData(typing: table | series, headers, rows, totals)`.

- Reports (FR-R): `coa`, `summary`, `monthly`, `quarterly`, `cash_flow`, `net_worth`
- All pure functions: money integer base → for display, `cents→'x,xxx.xx'` formatting helpers keep FP only
  at render boundaries (format-string only, NFR-10).
- Excel (`export/excel.py`): xlsxwriter, header freeze, currency col type number format
  `#,##0.00`, filename per AC-R7. PDF (`export/pdf.py`): WeasyPrint from jinja2 report template, page numbers in
  the footer via CSS `@page`.

### 4.9 Provider adapters (MarketDataProvider ABC)

```
get_quote(ticker) -> Quote(price, asof, source)
get_history(ticker, start, end) -> series[close, volume]
get_news(ticker, limit) -> list[NewsItem(title, url, source, summary, published)]
get_profile(ticker) -> Profile(name, exchange, sector or None, currency)
search(ticker_fragment) -> suggestions (used by add-brokerage 'search' in textarea)
```

- **YahooFinanceAdapter** uses public yfinance-compatible endpoints (unofficial, no SLA; D-10): page path caching via
  `price_cache`/`latest_quotes`, 15 min freshness windows (AC-I2a), exponential backoff, UA-supported statuses;
  marked as "unofficial, at-your-own-risk" in code and UI (AC-I2d).
- **ManualAdapter**: always-enabled no-network fallback — UI data entry writes to `latest_quotes` with `source='manual'`
  (AC-I2c precedence in `valuation.pick()`; manual entries survive until a *fresher* provider quote arrives).
- Registry: `PROVIDERS = {"yahoo": YahooAdapter, "manual": ManualAdapter}`; `provider.selected` setting routes;
  transport failures degrade to stale-cache badge, never crash (AC-I2b).

## 5. Frontend design (Next.js App Router)

### 5.1 Route tree

```
/                       → redirect /dashboard (auth-gated layout)
(auth)                  /login  /register          (public, redirects away when authed)
(app)                   (authed layout: mega menu shell)
  /accounts         list (dashboard summary + COA tree page component)
  /accounts/[id]    detail (balance, lines, sensitive detail w/ reveal)
  /accounts/new|edit
  /transactions     list → /transactions/new  /transactions/[id]
  /investments      overview: accounts & positions
  /investments/research         portfolio research landing (or redirect to portfolio page)
  /investments/analysis         portfolio analysis/optimization surfaces
  /investments/positions/[id]    → info news TA graphs (position screen)
  /investments/portfolio         analysis + optimization tabs
  /reports         Chooser page ↔ /reports/[kind] with URL params
  /users            FR-U4
  /settings         Profile / Data / Providers / Seeds / Audit tabs (FR-S)
  /settings/profile
  /settings/posting
  /settings/seed
  /settings/backup
  /settings/users
  /settings/audit
```

Auth gating: `app/(app)/layout` → `getSession()` server component; no-auth → `redirect('/login')`.
`/api` client (browser) wraps fetch with `X-Requested-With` header + 401 → route to login.

### 5.2 Navigation shell (FR-N + FR-X3 + FR-X4)

- `MegaMenu` component: DaisyUI navbar shell with an always-visible horizontal top-level nav; `nav` tree data is a TS constant mirroring
  [01 §10](01-requirements.md) and [01 §12](01-requirements.md), keyboard accessible (AC-N2/AC-X3d),
  route-parity highlight (AC-N4/AC-X3d/AC-X4d), and left-brand home link (`InvestFlow` → `/dashboard`).
- Post-ITER-16 IA target groups: Dashboard, Accounts (Chart of Accounts/Categories/Transactions),
  Investments (Portfolio Research/Analysis), Reporting, Settings (Profile/Posting/Seed Management/
  Backup and Download/Users/Audit). Each submenu item must bind to a route (AC-X3c).
- Post-ITER-19 refinement target (FR-X4): preserve the same top-level order in a horizontal navbar,
  and refine labels to Investments (Portfolio/Analysis/Research) and Settings (Backup and Downloads).
  Route owners and auth gating stay unchanged while aliases remain shell-consistent (AC-X4c/AC-X4d).
- Current interaction behavior (ITER-20 refinement): submenu groups open on hover/focus (not click-only), retain
  Escape-close support, and use a hover-safe close delay with flush submenu positioning to avoid pointer-gap collapse.
- Mega menu is one shared component (not per-page navigation), rendered fully client-side; server still
  passes sanitized `user` info only.

### 5.3 State & data fetching

- React Query v5: server state only; local modeling state (React state; no global store needed except `db` service).
- Mutations invalidate by key (`['tx','list']`, `['reports','net',…plot]`, etc.).
- Charts: SSE or polling — none; on-demand `refetch` only (simple app; AC-D4 refresh = refetch).

### 5.4 Design system

- Tailwind 4 with DaisyUI 5 components (btn, card, table, drawer, modal, tabs, select, slider, chart-lib).
- Theme: DaisyUI `winter` baseline (FR-X1), with future user overrides handled through Settings.
- Data tables: shared `DataTable` wrapper/adapters (FR-X2) over the selected open-source table engine; screen
  pages consume the wrapper rather than bespoke table implementations.
- Priority components: `Money` (int-cents formatted), `RevealField` (**encrypted masked**, AC-E6),
  `BalanceChart`, `FlowTable` (tx table with criterion), `CategoryPicker`.
- Typography: system-ui; contrast AA (NFR-7); min slot size 44px (AC-N3).

## 6. Security summary (NFR-3 / FR-E)

| Concern | Control |
|---|---|
| Password strength + storage | min 10 chars; argon2id (time=3, mem ≥ 64 MiB) |
| Session | JWT httpOnly SameSite cookie + epoch revocation |
| TLS/transport | localhost default; document reverse-proxy/TLS option for LAN; cookie `Secure` flag on non-dev |
| CSRF | SameSite=Lax + custom header check on mutations |
| Secrets at rest | AES-256-GCM, AAD-bound, versioned key IDs, keyfile 0600, no plaintext in DB/log/exports (AC-E1/E5/E7) |
| Brute force | per-user login throttle (AC-U2c), registration rate limit (AC-U1d) |
| Logs/audit | masked-only secrets summary (AC-E5, AC-S7) |
| Frontend bundles | no secrets, no ciphertext handling; decryption server-side only |

## 7. Operations

- **Backup** (AC-S6): `sqlite3 backup` API snapshot streamed with mimetype + filename
  `investflow-backup-<ts>.db` (Settings download button). Restore is documented as manual (replace file, restart)
  in `README`; a guided restore is deferred (gap analysis).
- **Migrations**: Alembic autogenerate during dev; every migration includes seed COA/category merge check.
- **Env vars**: `INVESTFLOW_DB_PATH`, `INVESTFLOW_JWT_SECRET`, `INVESTFLOW_ENC_KEYS`/`INVESTFLOW_ENC_KEY_FILE`,
  `INVESTFLOW_CORS_ORIGINS` (default dev), `PORT` (backend), `NEXT_PUBLIC_API_BASE`.
- **Port matrix**: `:3000` frontend, `:8000` backend; SQLite WAL; file-lock-friendly (`busy_timeout=5000`).
- **Rotation**: `make rotate-key` from §4.4; **`make seed`** idempotent COA seed; **`make test`** = pytest + vitest;
  **`make test-e2e`** Playwright.
