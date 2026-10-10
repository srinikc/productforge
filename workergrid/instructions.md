# WorkerGrid — Shared Worker Instructions (Charter)

> **This is the file `/wg instruct` edits.** Location: `workergrid/instructions.md`.
> Every worker session MUST load and follow these instructions for **every** backlog item it works.
> Append more with `/wg instruct <text>` (or edit here). Manual/editable — the common charter.

## Mode
- **Manual (default):** work step-by-step and **wait for the operator's input/approval** at every gate below.
  Nothing consequential proceeds without an explicit yes. The operator sees how the item is designed/executed
  and their inputs are applied. (`/wg work manual`)
- **Auto:** run the same lifecycle end-to-end and self-approve the gates. (`/wg work auto`)
- In BOTH modes the guidelines below are binding; only the *asking* differs.

## Guiding principle (every worker)
think → design → 360° check (dependency/impact) → backlog-needed → feature branch → code (no shortcuts) →
wire it → exercise it → record drift → approval (new path) → API-first → verify e2e.

## Guidelines (binding for every backlog item)
1. **Think → design → 360° check → backlog gate.** Confirm the work belongs to a real backlog item; check if an
   epic must be updated; ensure the item's context/fields are complete (objective, acceptance criteria, scope,
   affected files, deps, priority, analysis) before implementing.
2. **Feature branch → design/architecture → code (no shortcuts).** Everything is stitched/wired together and
   exercised; record any drift/divergence and any approval needed. Never commit to `develop`/`main` directly.
3. **Modular + scalable; API-first.** Review whether an API is required; if so, design and implement it; verify
   end-to-end. Prefer extending existing owners over new paths.
4. **Framework-agnostic.** No framework/vendor references in PF code, docs, or artifacts. The current dashboard
   is **legacy** — never reference it. One truth per concern, one writer per store.
5. **Issues → RCCA → backlog.** Any defect/issue found: raise it (`core/issues.py`), do a 5-Why RCCA + a new
   guard, record it in the backlog, and fix it **properly** (extend existing functionality; only design a new
   path when truly needed — and ask for approval with valid details).
6. **Summarize + IMPACT REVIEW + approval BEFORE implementation.** State in plain language what functionality it
   adds; produce the mandated IMPACT REVIEW table; get approval before implementing.
7. **Push to GitHub `develop`** only once validated (via the PF delivery lane; never force-push `develop`).
8. **Reconciliation before implementation** (binding for any change).
9. **Produce the RECONCILIATION block:** `PRIOR DECISIONS` / `EXISTING PATH` / `ASSUMPTIONS` / `DIVERGENCES` /
   `OPEN QUESTIONS`.
10. **No assumption is implemented unconfirmed.**
11. **No divergence is silent** — amend the recorded decision first.
12. **Decisions are an append-only ledger**, cited by implementations.
13. **Unknowns are investigated, never extrapolated** — grep/read the code (file:line) before proposing.
14. **Highlight risks** in the plan/implementation, with mitigation options.

## Full lifecycle (the worker architects/designs too — PF cannot build PF)
1. Understand the requirement + inspect current code.
2. Design + mandated **IMPACT REVIEW** table + RECONCILIATION block.
3. Implement on a **feature branch** (never `develop`/`main` directly).
4. Wire it (invoked on the runtime path); exercise it.
5. Gates: lint + precheck; link evidence on the backlog item.
6. Merge to `develop`; record delivery provenance.
7. Raise an issue + RCCA for any defect.

## Definition of Done
branch · lint clean · precheck PASS · evidence linked · merge · delivery provenance recorded.

## Process rules
one writer per store · RCCA for defects · dedup-before-add · **one working tree per session** · record drift ·
ask approval for new paths.

## Conventions
Follow `product-forge/AGENTS.md` (binding), `docs/STRUCTURE-CONTRACT.md`, `config/store-registry.json`.

## Escalation
Raise an issue (`core/issues.py`) with RCCA; ask the operator for approval on new/breaking paths.

---
<!-- Append worker-specific instructions below. -->
