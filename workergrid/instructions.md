# WorkerGrid — Shared Worker Instructions

> **This is the file `/wg instruct` edits.** Location: `workergrid/instructions.md`.
> Every worker session should load these instructions. Append more with `/wg instruct <text>` (or edit here).
> This file is **manual/editable** — it is the common charter each worker must follow.

## Guiding principle (every worker)
think → design → 360° check → backlog-needed → feature branch → code (no shortcuts) → wire →
exercise → record drift → approval (new-path) → API-first → verify e2e.

## Full lifecycle (workers must architect/design too)
PF cannot build PF, so a worker on a PF (or project) dev task does the **whole** lifecycle:
1. Understand the requirement + inspect current code.
2. Design + mandated **IMPACT REVIEW** table.
3. Implement on a **feature branch** (never commit to develop/main directly).
4. Wire it (invoked on the runtime path); exercise it.
5. Gates: lint + precheck; link evidence on the backlog item.
6. Merge to `develop`; record delivery provenance.
7. Raise issue + RCCA for any defect.

## Definition of Done
branch · lint clean · precheck PASS · evidence linked · merge · delivery provenance recorded.

## Process rules
one writer per store · RCCA for defects · dedup-before-add · **one working tree per session** ·
record drift · ask approval for new paths.

## Conventions
Follow `product-forge/AGENTS.md` (binding), `docs/STRUCTURE-CONTRACT.md`, `config/store-registry.json`.

## Escalation
Raise an issue (`core/issues.py`) with RCCA; ask the operator for approval on new/breaking paths.

---
<!-- Append worker-specific instructions below. -->
