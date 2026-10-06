# PF Baseline Freeze

**Item:** BI-PF-0392 (Epic A / A0) · **Status:** frozen baseline for the target-architecture program.

## Baseline
| Field | Value |
|---|---|
| Date | 2026-10-06 |
| Integration branch | `develop` |
| Frozen SHA | `d3e44b9` |
| Language footprint | Python-only (0 Go / 0 Rust); dashboard Python (`dashboard/server.py`) |
| Test baseline | full pipeline suite green (848 passed, 1 skipped at last full run) |
| Gate baseline | `precheck.py` (fast) PASS; `precheck.py --full` available at merge/release |

> Freeze means: this SHA is the reference point. No feature work is mixed into A0; the program builds on top.

## Reconciliation of the source architecture document
Source: `docs/Product_Forge_Code_Aligned_Target_Architecture_PreImplementation_Baseline.md`
- The **CODE-ALIGNED AMENDMENT** (source §3038+) is the **authority** wherever it conflicts with earlier sections.
- The **working authority** for this program is `docs/PF-TARGET-ARCHITECTURE-AND-IP-PLAN.md` (consolidated plan).
- **Inconsistency noted & resolved:** the source baseline says "39-stage/8-phase pipeline" (line 11) while the
  amendment §T says "16-stage Factory Pipeline". Resolution: the **actual repo pipeline is the authority**;
  stage-count references in prose are descriptive, not contractual. Do not treat either number as a contract.
- **Scope clarification:** this program is about the **PF platform itself** (the factory that produces
  products). The generated product's runtime and any EAP *executor* are a **separate, parked** concern.

## Frozen decisions (see ADR register)
- `docs/ARCHITECTURE-DECISIONS.md` → **ADR-0001: Go-first compiled delivery** (one source, many editions; new
  features → Go; existing → compiled; no raw `.py`).
- Delivery strategy: `BI-PF-0387` (baseline) · ADR: `BI-PF-0388` · IP-value: `BI-PF-0386`.

## Program epics
- **Epic A** `BI-PF-0390` — PF Commercial & IP Foundation (A0–A7 + B1).
- **Epic B** `BI-PF-0391` — PF Scale & Editions (B2–B7, Bmig; trigger-gated).
