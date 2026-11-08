# InvestFlow — 05 · Defects

| | |
|---|---|
| **Status** | Rolling document — update at the end of **every** iteration ([07-iterative-prompts](07-iterative-prompts.md) §2) |
| **Last updated** | 2026-11-08 (initial; register empty) |

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

*(Empty — first entry expected no later than ITER-01 smoke-test E2E runs.)*

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
