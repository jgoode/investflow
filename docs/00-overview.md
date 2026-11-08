# InvestFlow — 00 · Overview

| | |
|---|---|
| **Status** | Active |
| **Last updated** | 2026-11-08 |
| **Primary docs** | [01-requirements](01-requirements.md) · [02-architecture](02-architecture.md) · [03-test-plan](03-test-plan.md) |

## 1. Vision

**InvestFlow** is a simple personal accounting application that runs in the browser on a single machine
(FastAPI backend + Next.js frontend). It helps one household track its money:

- A **double-entry ledger** with a seeded, editable **chart of accounts** and flexible **categories**.
- A headline focus on **cash flow** (money in vs. money out over time) and **net worth**
  (assets incl. holdings at market value − liabilities), surfaced first on the dashboard and drillable into reports.
- **Investment management**: positions held inside brokerage/cash accounts, live quotes and news from
  Yahoo Finance (unofficial endpoints) with manual fallback, technical indicators, portfolio analysis and
  mean-variance optimization.
- **Robust reporting** with export to Excel (xlsx) and PDF.
- **Sensitive account details** (account numbers, transfer numbers, etc.) are **encrypted at rest** with
  application-layer field encryption; SQLite never stores them in plaintext.

It is deliberately *simple*: single currency, single role, no budgets, no multi-tenant separation.
It is deliberately *rigorous* where it matters: real double-entry, field-level crypto, tested acceptance criteria.

## 2. Product decisions (recorded during interactive design session, 2026-11-08)

| # | Decision | Rationale |
|---|----------|-----------|
| D-01 | Delivered as a **local web app** (start backend + frontend, open browser). No Electron/Tauri wrapper. | User chose simplest path; wrapper is a future consideration. |
| D-02 | **Multi-user, shared book**: all registered users share one ledger. | Household-style use; no per-user data isolation. |
| D-03 | **Open self-registration**; all users are **equal** (single role, no admin/anal/member tiers). | Simplest viable model. |
| D-04 | **True double-entry** accounting internally; UI keeps posting simple (credit/debit legs auto-balanced where sensible). | Rigor now, options later. |
| D-05 | **Single currency** (USD default, configurable label in Settings). No FX. | Simplicity. |
| D-06 | **Budgets dropped** from scope (despite original feature list). Recorded in [06-gap-analysis](06-gap-analysis.md). | User decision 2026-11-08. |
| D-07 | **Net worth = account balances + holdings at current market value − liabilities.** Ledger is not auto-revalued; holdings are valued at report time. | Avoids fake revaluation entries polluting the ledger. |
| D-08 | **Positions live inside COA accounts** (brokerage/cash accounts of investment subtype); no separate investment module. | One source of truth. |
| D-09 | **Average cost** basis for position P&L; FIFO lots deferred to gap analysis. | User decision. |
| D-10 | Market data + news from **Yahoo Finance unofficial endpoints**, behind a **provider adapter interface**; manual price entry always available. | Free; adapter protects against instability of the unofficial API. |
| D-11 | **App-layer AES-256-GCM field encryption** for sensitive columns; key from env var/key file; SQLite stays a plain file. | Chosen over SQLCipher. |
| D-12 | Settings screen: profile, provider/key config, currency display, defaults, **plus admin extras** (COA seed management, backup/restore helpers, audit log viewer). | User decision. |
| D-13 | Technical analysis = baseline set: SMA, EMA, RSI, MACD, Bollinger Bands, volume. | User decision. |
| D-14 | Portfolio optimization = **mean-variance**: efficient frontier, max-Sharpe, min-variance. | User decision. |
| D-15 | Development is a **strict TDD process** in **16 thin iterations**; docs roll forward after each iteration. | User choice: many small iterations. |
| D-16 | Standards stack locked (see [02-architecture](02-architecture.md) §2): Next.js 15 App Router, React 19, Tailwind 4 + DaisyUI 5, Python 3.11, FastAPI, SQLAlchemy 2 + Alembic, argon2, JWT httpOnly cookie, xlsxwriter, WeasyPrint, Recharts, lightweight-charts. | User approved defaults. |

## 3. Non-goals

- No per-user data isolation; one shared book.
- No budgets or budget-vs-actual targets.
- No multi-currency, FX, or tax-form generation.
- No mobile native app (responsive web is enough).
- No cloud deployment story in v1; single machine, local execution.
- No FIFO/tax-lot accounting (deferred, see gap analysis).
- No commercial SLAs for market data — Yahoo unofficial endpoints are best-effort.
- No ERP-grade audit (a lightweight audit log table only).

## 4. Feature map

| Area | Highlights | Requirement IDs |
|------|-----------|-----------------|
| Auth & users | Registration, login, sessions, user list, activate/deactivate | FR-U |
| Chart of accounts | Seed COA, tree, CRUD, archive, encrypted account details | FR-C, FR-K |
| Categories | Income/expense tag set, per-line assignment | FR-K |
| Transactions | Simple credit/debit posting, transfers, edit/void, filters | FR-T |
| Investments | Positions in brokerage accounts, average cost, valuation, quotes, news, TA, portfolio analysis, optimization | FR-I |
| Reporting | COA, summary, monthly, quarterly, cash flow, net worth, XLSX/PDF export | FR-R |
| Dashboard | Net worth & cash flow cards, drill to reports | FR-D |
| Settings | Profile, provider key, defaults, seed mgmt, backup/restore, audit viewer | FR-S |
| Security | Field encryption at rest, argon2 + JWT cookie, audit log | FR-E, NFR |

## 5. Document index

| File | Purpose |
|------|---------|
| `00-overview.md` | Vision, decisions, non-goals, index (this file) |
| `01-requirements.md` | Functional + non-functional requirements with Given/When/Then acceptance criteria |
| `02-architecture.md` | Stack, data model, encryption, auth, adapters, frontend structure, API surface |
| `03-test-plan.md` | Test strategy, layers, coverage, traceability matrix to requirements |
| `04-progress.md` | Iteration roadmap and rolling progress log |
| `05-defects.md` | Defect register, severity/priority workflow |
| `06-gap-analysis.md` | Requirements vs planned scope; deferred items register |
| `07-iterative-prompts.md` | Roll-forward doc workflow + paste-ready iteration prompts |
| `08-backlog.md` | Backlog: future feature requests + deferred work (incl. FEAT-001 portfolio CSV import) |

## 6. Glossary

| Term | Meaning |
|------|---------|
| **Book** | The single shared ledger all users record into. |
| **COA** | Chart of accounts — tree of accounts (asset, liability, income, expense, equity). |
| **Credit / Debit** | Ledger directions of a transaction line. Debits increase assets/expenses; credits increase liabilities/income/equity. |
| **Transfer** | Transaction with a debit line and a credit line against two asset/liability accounts. |
| **Position** | Holding of N shares of a ticker inside one investment account, with an average cost. |
| **Cash flow** | Income − expense movements over a period (transaction-based). |
| **Net worth** | Asset account balances + Σ (position quantity × current market price per brokerage account) − liability account balances. |
| **Mega menu** | Top navigation bar with drop-down groups (Dashboard, Accounts, Investments, Reports, Users, Settings). |
| **Iteration** | One thin vertical slice (ITER-01…ITER-16) ending with failing-first tests passing end to end. |
