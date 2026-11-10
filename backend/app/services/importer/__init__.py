"""Portfolio CSV import core — FR-IMP-1 (backend/app/services/importer/).

Modules:
    parser    — CSV parsing, schema checks, decimal→scaled-int conversion (NFR-10: no floats)
    mapping   — column-mapping resolution + shipped starter templates (AC-IMP1a)
    dedupe    — trade hash-tuple + replay-order validation (AC-IMP1c/AC-IMP1e)
    evaluator — dry-run preview construction (AC-IMP1b)
    service   — commit orchestration: atomic per-file posting through the
                existing posting service only (AC-IMP1c/1d/1e/1g)

Decision record (ADR-008, docs/04 §4): buy/sell trade rows update positions
through the avg-cost engine only — they never write ledger lines; dividend/fee
rows post real two-leg cash events through the existing posting service.
"""

from __future__ import annotations
