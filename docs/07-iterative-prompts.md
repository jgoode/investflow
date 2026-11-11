# InvestFlow — 07 · Iterative Prompts & Roll-Forward Workflow

| | |
|---|---|
| **Status** | Living document — §4 is **regenerated at the end of every iteration**; §3/§5 stay stable |
| **Last updated** | 2026-11-10 (ITER-23 ✅ closed; §4 → next iteration **unscheduled** — pending user backlog review) |

This document is the operator's manual for driving InvestFlow development as a sequence of
**interactive, test-driven iterations** in coding sessions. It contains:

- §2 — the documentation roll-forward workflow (what to update after every iteration)
- §3 — the in-session TDD execution loop
- §4 — **the copy-paste-ready prompt for the next iteration** (currently ITER-23)
- §5 — the stable prompt template used to generate §4 for later iterations

---

## 2. Roll-forward documentation workflow (end of every iteration)

Execute in this exact order at iteration close, before starting the next iteration:

| Step | Doc | Action |
|---|---|---|
| R1 | `04-progress.md` | Set iteration row status → ✅/⏸; append a dated progress-log entry per §3 template there; add any new ADR rows |
| R2 | `05-defects.md` | Triage all open entries opened during this iteration (fill State/severity); verify every deferred-open has a [06](06-gap-analysis.md) row |
| R3 | `06-gap-analysis.md` | Add GAP rows for any spec-vs-reality drift discovered; update §4 close-of-iteration status sentence; promote schedulable rows |
| R4 | `01-requirements.md` / `02-architecture.md` | Apply any spec changes the iteration proved necessary — **each change gets an ADR row in 04 §4** (no silent edits) |
| R5 | `07-iterative-prompts.md` | Replace §4 with the next iteration's prompt (built from template §5); bump "Last updated" |
| R6 | `docs/00-overview.md` | Only if a decision/state_table row changed (D-xx) — otherwise untouched |
| R7 | Cross-check | [03-test-plan](03-test-plan.md) §4 matrix: mark the iteration's AC columns as tested in the matrix notes (no structural change) |
| R8 | `08-backlog.md` | If the iteration promoted, scheduled, or was affected by a backlog item (esp. FEAT-001), update its row/lifecycle state; otherwise untouched |

Roll-forward rule: **docs are never edited silently** — the progress-log entry (R1) lists every doc delta
with a one-line reason. If a doc edit is speculation rather than proved-by-tests, it goes in
[06-gap-analysis](06-gap-analysis.md), not into the spec.

## 3. In-session TDD execution loop

```
1. LOAD docs:           read 04-progress (roadmap row status), the iteration's ACs in 01,
                        architecture sections listed in 04 §5 mapping row
2. CONFIRM scope:       restate the iteration deliverable + AC ids to the user; ask questions on
                        any ambiguity — never assume
3. WRITE RED tests:     backend L1/L2 + frontend L3 (+ L4 E2E scenario) per 03 §4 mapping
4. RUN make test →      verify failures are for the right reasons; record "initial fail" snapshot
5. IMPLEMENT minimal:   backend slice then frontend slice; no scope creep beyond iteration ACs
6. GREEN:               make test && make test-e2e; fix via defects workflow if discovered bugs (05)
7. REFACTOR + LINT:     ruff/mypy/eslint/tsc; coverage vs 03 §6 targets
8. ROLL FORWARD:        execute §2 checklist (R1–R8)
9. HANDOFF:             report status; user confirms; next session starts with new §4 prompt
```

Session boundaries: one iteration per session is normal; ITER-02–03 may combine **only** if all ACs of
ITER-02 are already green.

## 4. Paste-ready prompt — current next iteration

> **⚠ Not scheduled yet.** The ITER-23 prompt was spent; the roadmap queue ([04 §2A](04-progress.md)) is
> exhausted. The only specified-but-unscheduled backlog item is **FEAT-002** (non-investment opening
> balances + statement migration import — [08 §3D](08-backlog.md), shares the importer core of FEAT-001).
> Per the backlog lifecycle rule (scheduling is the user's call, [08 §4](08-backlog.md)), §4 stays a
> placeholder until the user schedules the next iteration in a backlog-review session. When scheduled:
> promote the §3D.3 rows into `01-requirements.md` FR/AC ids, add the roadmap row in 04 §2A, and regenerate
> this §4 from the template in §5 below.

*(No paste-ready prompt is current. Run the scheduling step first — see the note above.)*

## 5. Stable iteration prompt template (used by R5 to build §4)

```
> **ITER-XX — <title>**
>
> You are working in the InvestFlow monorepo. Read first: docs/00 (decisions D-…), docs/01 §<req sections>,
> docs/02 §<arch sections>, docs/03 §4 matrix row for this iteration, docs/04 ITER-XX row.
>
> **This is an interactive TDD session.** Tests before code. Scope only to this iteration's AC list:
> <list the AC ids e.g. AC-T1, AC-T2, AC-T3…> — ask me about any ambiguity; never assume.
>
> **Deliverable:** <2–6 numbered thin-slice deliverables, each mapped to ACs>
> **Out of scope this iteration:** <explicitly listed deferred items, links to 06 gap rows>
> **Definition of done:** mapped-layer tests green, lint/types pass, coverage targets met for touched code,
> then roll-forward workflow docs/07 §2 R1–R8 so the next prompt (§4) is ready.
> **Known traps (if any):** <phase-specific notes, e.g., "crypto battery from 03 §5.2 must keep passing" — reference tests>
```

## 6. Queue of prepared prompts (built but not yet "current")

*(R5 moves one row from here into §4, replacing the spent one. Do not skip order without a `04-progress.md` note.)*

- ✅ **ITER-05 — Chart of accounts** (FR-C; architecture §3.1 accounts/account_sensitive, §3.3 seed, §5.1; traps:
  idempotent seed re-apply merges additions only, AAD binding regression set from ITER-04 must stay green,
  finalize mega menu six groups)
- ✅ **ITER-06 — Categories** (FR-K; §3.1 categories; traps: delete → "(uncategorized)" never destroys history)
- ✅ **ITER-07 — Simple transactions** (FR-T1–T3/5/9; §4.5 posting service; traps: imbalance atomicity,
  server-side balance check is final authority)
- ✅ **ITER-08 — Transfers/edit/void/audit** (FR-T4/6/7/8/10; §4.5+audit_log; traps: void excluded by default
  from reports from now on — regression pin)
- ✅ **ITER-09 — Reports core** (FR-R1–R4/R9/R10, NFR-9; §4.8 reporting engine; traps: report = second
  implementation cross-check per 03 §5.3, DST property tests)
- ✅ **ITER-10 — Cash flow, net worth, exports** (FR-R5–R8, NFR-4; §4.8/§4.9 exports; traps: xlsx/pdf cross-checks,
  first perf benchmark)
- ✅ **ITER-11 — Dashboard** (FR-D; §5.1/§5.3; traps: ≤2 batched calls AC-D3, drill deep links, onboarding states)
- ✅ **ITER-12 — Investment accounts & positions** (FR-I1, AC-I3a manual; §4.6, §3.1 positions; traps: avg-cost
  property tests per 03 §4 row, oversell 422, quantity ×10⁴ scaling)
- ✅ **ITER-13 — Market data adapter** (FR-I2; §4.9 providers; traps: 15-minute freshness, manual precedence,
  stale-badge behavior)
- ✅ **ITER-14 — Position detail + news + TA** (FR-I3/I4/I5; §4.6; traps: insufficient-data handling,
  deterministic TA fixtures, provider-failure degrade path)
- ✅ **ITER-15 — Portfolio analysis + optimization** (FR-I6/I7; §4.7 mvo; traps: ≥120-day gate AC-I7c,
  constraint infeasibility wording, advisory-only disclaimer) — closed in this roll-forward pass
- ✅ **ITER-16 — Settings & polish** (FR-S, NFR-4 re-bench, NFR-7 audit; §7 ops; traps: backup download-only,
  seed merge re-check, full benchmark re-run, a11y pass closure)
- ⏭ **ITER-17 — Winter theme baseline** (FR-X1, NFR-7; §5.4 design system; traps: theme-only scope,
  keep focus/contrast regressions at zero)
- ⏭ **ITER-18 — Data table standardization** (FR-X2, NFR-4/NFR-7; §5.3/§5.4; traps: choose OSS table via
  explicit scorecard, stage migrations users/transactions/accounts, avoid big-bang rewrite)
- ✅ **ITER-19 — Navbar IA redesign** (FR-X3 + FR-N; §5.1/§5.2; traps: exact hierarchy, no dead submenu links,
  route highlight + keyboard semantics preserved)
- ✅ **ITER-20 — Horizontal navbar IA refinement** (FR-X4 + FR-N; §5.1/§5.2; traps: strict top-level order,
  Investments label split to Portfolio/Analysis/Research, and Settings label update to Backup and Downloads) — closed at ITER-21 (gates/docs)
- ✅ **ITER-21 — Navbar IA stabilization and closeout** (FR-X4 validation, Escape focus-return, navbar L4 reachability; ITER-19/20 closeout) — see §4 roll-forward history
