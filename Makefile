# InvestFlow — root Makefile (docs/02-architecture.md §7 + §2 layout)
# Targets: setup, dev, test, test-e2e, lint, migrate  (per docs/07 §4 deliverable 4)

SHELL := /bin/bash
.PHONY: setup dev dev-backend dev-frontend test test-backend test-frontend test-e2e lint lint-backend lint-frontend migrate

## setup  — install both toolchains (idempotent)
setup:
	cd backend && uv sync
	cd frontend && pnpm install
	pnpm install
	pnpm exec playwright install chromium

## dev    — run backend (:8000) and frontend (:3000) together (NFR-1)
dev:
	$(MAKE) -j 2 --no-print-directory dev-backend dev-frontend

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && pnpm dev

## test   — backend pytest + frontend vitest (docs/03 §2 L1/L2 + L3)
test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest

test-frontend:
	cd frontend && pnpm exec vitest run

## test-e2e — Playwright L4 (docs/03 §2 L4); starts both web servers itself
test-e2e:
	pnpm exec playwright test

## lint   — ruff + mypy (backend), eslint flat + tsc --noEmit (frontend) (NFR-6)
lint: lint-backend lint-frontend

lint-backend:
	cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy app

lint-frontend:
	pnpm --dir frontend exec eslint . && pnpm --dir frontend exec tsc --noEmit

## migrate — run Alembic migrations (02 §7)
migrate:
	cd backend && uv run alembic upgrade head
