# InvestFlow

Personal accounting app (double-entry ledger, investments, reporting) — FastAPI backend +
Next.js frontend on SQLite. See `docs/00-overview.md` for the vision and `docs/` for
requirements (`01`), architecture (`02`), test plan (`03`), and progress (`04`).

## Quickstart (NFR-1: ≤ 3 commands)

```sh
make setup   # installs Python (uv) + Node (pnpm) toolchains, idempotent
make dev     # backend on http://localhost:8000 · frontend on http://localhost:3000
# open http://localhost:3000
```

`make dev` runs two processes together; press Ctrl-C twice (or `pkill -f "uvicorn app.main"`)
to stop. Single-machine local app — no cloud deployment is involved (NFR-1).

## Commands

| Command | What it does |
|---|---|
| `make setup` | Install backend deps (`uv sync`), frontend deps (`pnpm install`), Playwright chromium |
| `make dev` | Backend `uvicorn app.main:app --reload` (:8000) + Next.js dev server (:3000) |
| `make test` | Backend pytest (`backend/tests/**`) + frontend vitest (`frontend/**__tests__/**`) |
| `make test-e2e` | Playwright smoke suite (`e2e/**`) against the stacked real stack |
| `make lint` | ruff + mypy strict (backend) · eslint flat + `tsc --noEmit` (frontend) |
| `make migrate` | `alembic upgrade head` (database location: `INVESTFLOW_DB_PATH` or `backend/data/investflow.db`) |

## Layout (docs/02-architecture.md §2)

```
investflow/
├─ backend/    FastAPI app (package `app`), pytest suite, Alembic
├─ frontend/   Next.js 15 App Router + Tailwind 4 + DaisyUI 5, vitest suite
├─ e2e/        Playwright L4 suite
├─ docs/       documentation set
└─ Makefile
```

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| `INVESTFLOW_DB_PATH` | `backend/data/investflow.db` | SQLite file location |
| `PORT` | `8000` | backend port |
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000` | API base for the frontend (bundler-time) |
