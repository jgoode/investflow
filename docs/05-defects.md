# InvestFlow — 05 · Defects

| | |
|---|---|
| **Status** | Rolling document — update at the end of **every** iteration ([07-iterative-prompts](07-iterative-prompts.md) §2) |
| **Last updated** | 2026-11-10 (ITER-23 close review: no new defects — the three red-phase test-authoring slips were corrected in the red tests themselves before implementation, ITER-01 precedent; DEF-001–DEF-004 remain verified-closed) |

## 1. Definitions

- **Defect**: any behavior violating an AC in [01-requirements](01-requirements.md), an invariant in
  [02-architecture](02-architecture.md), or a test expectation. A discovered-but-unimplemented AC is **not**
  a defect — it belongs to [06-gap-analysis](06-gap-analysis.md) unless it was marked Done previously.
- **Regression**: a defect that re-opens after being closed. Regression closure requires its permanent
  guard test ([03 §8](03-test-plan.md) rule 3).
- **Flaky test**: failure not reproducible on 3/3 runs under pinned env conditions.

## 2. Severity & priority

| Severity | Definition | Fix expectation |
|---|---|---|
| **S1 Critical** | Data corruption, ledger imbalance, plaintext secrets exposed (E-failures), unauthenticated access possible, money arithmetic drift | Fix blocks all further iterations — no "next iter" deferral |
| **S2 Major** | Feature-blocking wrong values/concurrency errors (e.g., atomic write lost, Throttle/epoch failures, provider mis-fallback), non-trivial a11y blockers | Fix before closing the current iteration |
| **S3 Minor** | Cosmetic, edge-case UX, perf < target but not user-noticeable, doc drift | May defer max 2 iterations with a [06-gap](06-gap-analysis.md) note |
| **S4 Trivial** | Wording/style | Batch fixes; do at next polish pass (ITER-16) |

Priority = severity × scope: any S1 anywhere > S2 core ledger/crypto/auth > S2 elsewhere > S3/S4.

## 3. Register (append-only)

ID pattern: `DEF-<three digits>`; never reused; a superseded row links the replacement instead of being deleted.

**ITER-01 close note:** at iteration close the register was empty (no red tests parked; a red-phase
test-authoring slip was caught by ruff `B018` before any test run, so not a defect). Post-close CI
verification (same date) produced **DEF-001** below.

### DEF-001 — CI: pnpm version conflict (`@pnpm/action-setup` explicit `version` vs `packageManager`)
- **Opened:** 2026-11-08 (ITER-01 CI verification) · **Severity:** S3 · **State:** verified-closed
- **Discovered by:** GitHub Actions run of `.github/workflows/ci.yml` (frontend job) — `Error: Multiple versions of pnpm specified` / `ERR_PNPM_BAD_PM_VERSION`
- **Layer/Component:** infra/CI
- **Evidence:** Actions log: version `12` from the workflow's `pnpm/action-setup` input vs `pnpm@12.16.1` in root `package.json` `packageManager`
- **Diagnosis:** `pnpm/action-setup@v4` already resolves the version from `packageManager`; the explicit `with: version: 12` conflicted with it.
- **Fix plan:** remove the explicit `version` input from both `frontend` and `e2e` jobs → action derives the exact pinned version from `packageManager`. Guard: the e2e job itself (installs via pnpm and runs the smoke suite) plus job startup logs show a single resolved version.
- **Verification:** 2026-11-08 — re-run of the suite after push; jobs resolve `pnpm@12.16.1` once.
- **Linked:** commit REC (this fix landed with DEF entry); no spec/AC impact ([01](01-requirements.md) untouched)

### DEF-002 — CI: `ERR_PNPM_IGNORED_BUILDS` (fatal) on frontend install — esbuild allow-list in wrong config home
- **Opened:** 2026-11-08 (post-DEF-001 CI re-run) · **Severity:** S3 · **State:** verified-closed
- **Discovered by:** GitHub Actions run of `.github/workflows/ci.yml` (frontend `pnpm install` step, exit 1)
- **Layer/Component:** infra/CI · frontend tooling
- **Evidence:** Actions log: `Error: ERR_PNPM_IGNORED_BUILDS … Ignored build scripts: esbuild@0.28.2`
- **Diagnosis:** pnpm 12 moved build-script allow-lists out of `package.json` (`pnpm` field reads only a deprecation warning) and renamed `onlyBuiltDependencies` → **`allowBuilds`** (pnpm.io/settings/build). Local runs only warned; CI (`strictDepBuilds=true` default) makes unreviewed builds fatal. The allow-list therefore never took effect from `package.json`.
- **Fix plan:** create `frontend/pnpm-workspace.yaml` with `allowBuilds: {esbuild: true}`; delete the dead `pnpm.onlyBuiltDependencies` field from `frontend/package.json`. Guard: CI-mode cold install (`CI=true pnpm install` from empty `node_modules`) passes, vitest suite still runs.
- **Verification:** 2026-11-08 — local cold install + `CI=true` exit 0; next Actions run after push.
- **Linked:** commits REC (fix + doc in same commit); follows DEF-001 (same CI surface); settings doc: pnpm.io/settings/build

### DEF-003 — E2E: `getByLabel('Flow')` strict-mode collision with navbar brand link aria-label
- **Opened:** 2026-11-10 (ITER-21 close, `make test-e2e` gate rerun) · **Severity:** S3 · **State:** verified-closed
- **Discovered by:** `e2e/smoke.spec.ts` categories CRUD flow — `locator.selectOption: strict mode violation: getByLabel('Flow') resolved to 2 elements`
- **Layer/Component:** e2e/helpers · frontend shell (navbar)
- **Evidence:** `test-results/smoke-categories-CRUD-flow-with-default-account/error-context.md`; snapshot in `docs/logs/iter-21/red-frontend-first-run.log` narrative — resolved elements: `<a aria-label="InvestFlow home">` (navbar brand link) and the categories `<select aria-label="Flow">`
- **Diagnosis:** ITER-20's left brand link (`aria-label="InvestFlow home"`) contains the substring "Flow"; Playwright `getByLabel` is substring-matching by default, so the pre-existing categories selector became ambiguous once the shell change landed (ITER-20 parked its E2E gate rerun, so this slipped to the ITER-21 closeout gate).
- **Fix plan:** pin the categories flow selector to `getByLabel("Flow", { exact: true })` (same accessible name, element unchanged); regression guard is the categories flow itself plus the new ITER-21 navbar reachability scenario which asserts the brand link by its accessible name. No UI/DOM change; no a11y regression (the brand label is correct).
- **Verification:** 2026-11-10 — `make test-e2e` 6/6 green after fix (snapshot `docs/logs/iter-21/green-e2e.log`); re-open condition: any future aria-label introducing a substring collision with a form-control label.
- **Linked:** [01 §12 FR-X4](01-requirements.md) (brand-link slice), [02 §5.2](02-architecture.md); ITER-20/ITER-21 rows in [04 §3](04-progress.md); no ADR (no spec change)

### DEF-004 — Backend suite: helper-level tests read/write the dev DB (`INVESTFLOW_DB_PATH` fallback)
- **Opened:** 2026-11-10 (ITER-22 close, `make test` gate rerun) · **Severity:** S3 (test-suite flakiness, no product impact) · **State:** verified-closed
- **Discovered by:** `tests/api/test_portfolio.py::test_portfolio_helper_and_summary_edge_cases` asserting `build_portfolio_summary()` is empty — failed after the ITER-22 e2e run left real imported positions in `backend/data/investflow.db`; the new L1 importer dedupe test likewise wrote `import_rows` into the dev DB (no fixture isolation → default DB path).
- **Layer/Component:** backend test suite (L1/L2 helper-level tests without the `client` fixture)
- **Diagnosis:** tests that call domain functions directly (no `client` fixture) never set `INVESTFLOW_DB_PATH`, so `app.db.connection.connect()` falls back to the gitignored dev DB; any state created there (e2e leftovers, prior test writes) leaks into assertions and makes the suite order/environment-dependent. Latent since the suite always ran against an empty dev DB.
- **Fix plan:** isolate both tests with `monkeypatch.setenv("INVESTFLOW_DB_PATH", str(tmp_path / …))` (the same env var the conftest client fixture uses); no product code change.
- **Verification:** 2026-11-10 — `make test` green (124 backend passed) after fix; re-open condition: any new helper-level test that touches `connect()` without env isolation.
- **Linked:** [04 §3](04-progress.md) ITER-22 entry (🐞 line); no ADR (no spec change)

### Entry template

```
### DEF-NNN — <one-line title>
- **Opened:** YYYY-MM-DD (ITER-XX) · **Severity:** S? · **State:** open → in-progress → verified-closed / deferred-open / wontfix
- **Discovered by:** test id (e.g. AC-T4/I) + file/test name, or manual/E2E path
- **Layer/Component:** e.g. backend/crypto · backend/ledger · frontend/megamenu · infra
- **Evidence:** red-test run snippet, stack-trace condensed (secrets masked!), screenshot path
- **Diagnosis:** root cause in one sentence + affected paths (files/function names)
- **Fix plan:** description + which tests must pass + regression test id created (REG-TEST-NNN …)
- **Verification:** date closed, `make test`/`make test-e2e` output refs, re-open conditions
- **Linked:** docs rows touched ([01]/[02]/[06] section ids), ADR row refs in [04 §4](04-progress.md)
```

## 4. Workflow

```
discovered (red test fails / manual / E2E)
   └→ document entry (template §3) — severity per §2
        ├─ S1: halt iteration; fix immediately with failing-first new test; then resume
        ├─ S2: fix within the iteration (keep the red test open until fixed)
        └─ S3/S4: mark deferred-open with target iteration; add row in [06 §3 deferred](06-gap-analysis.md)
verify: original red test green + regression test kept + no new red tests
   └→ update status row + [04-progress](04-progress.md) iteration entry (🐞 lines) + [06] if deferred
```

Rules:

1. **Never** delete or skip a failing test to close a defect — the test is evidence ([03 §8](03-test-plan.md)).
2. All defect-related log snippets are **secret-masked** (masking policy of [02 §6](02-architecture.md));
   an unmasked log paste in the defect docs is itself an S1 leak that must get its own DEF entry.
3. When a defect reveals a **requirements change** (spec was wrong, not the code), the fix lands as an explicit
   edit in [01](01-requirements.md)/[02](02-architecture.md) with an ADR row in [04 §4](04-progress.md) —
   the defect stays linked to proof-of-old-spec.
4. At the end of every iteration the register must be fully triaged: zero entries lacking a State/severity.

## 5. Standing validation checks (run each iteration close)

- All defect entries clean (§3 table fully triaged: every row has State + Severity).
- All "deferred-open" rows have a matching [06-gap-analysis](06-gap-analysis.md) §3 entry with iteration target.
- [04-progress](04-progress.md) `🐞 New defects` lines ↔ [05](05-defects.md) opened dates match the same iteration window.
