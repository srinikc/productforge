# Correction Ledger (SSOT)

Every human (HIL) correction becomes a **durable rule/guard** so the same divergence cannot recur silently.
This is the accountability + learning record for model-assisted engineering. Binding with
`docs/MODEL-ASSISTED-ENGINEERING.md`, `docs/RAG-PROCESS-MEMORY.md`, `docs/RCCA_productForge.md`.

## 1. Purpose
Turn "sorry, we discovered that was wrong" into a **system rule** — so the fix outlives the session and the model's
short-lived memory. A correction that recurs means the ledger/rule isn't working (see evaluation).

## 2. Entry schema
```
id            CL-<nnn>            (or reuse the backlog/defect id)
date          YYYY-MM-DD
context       item / epic / PR where it happened
expected      what HIL expected
delivered     what the model did
root_cause    the bias/gap (e.g. anchoring, silent gap-fill, unpinned term)
correction    the new RULE/GUARD (imperative, testable)
enforcement   where it is enforced (doc/SSOT | gate script | ADR | glossary)
status        active | superseded
```

## 3. When an entry is created
- On **every HIL correction** to a design/implementation/decision.
- On **every defect** via RCCA (5-Why + a new guard).
- When a term/expectation ambiguity caused rework.

## 4. How entries are enforced
A correction is only real if it lands somewhere the model/environment reads **every time**:
- a **rule** in a SSOT (EOS, review-gates, this set),
- a **gate** script (machine-checked, in precheck),
- an **ADR** (durable decision),
- a **glossary** term (definitions).
If none applies, the correction is not done.

## 5. How it feeds RAG
Ledger entries are an indexed source (`type=correction`) and are **retrieved + injected at task start / gates**
(`docs/RAG-PROCESS-MEMORY.md`). Contradictions with an active entry **STOP** the change.

## 6. Seed entries (from the audits that created this SSOT)
| id | correction (rule) | enforcement |
|---|---|---|
| CL-001 | **Route-by-kind/ownership before adding anything** ("who owns this? single writer? register it") | ownership gate (pending) + AGENTS.md |
| CL-002 | **Findings = reviewer-owned; dispositions = main-thread-owned** (keep the reviewer tool reviewer-only) | `docs/REVIEW-GATES-LIFECYCLE.md` + review tooling |
| CL-003 | **Define terms before building** (pin API/server/token/service…) | `docs/GLOSSARY.md` |
| CL-004 | **Don't delegate small decisions to sub-agents**; delegate only large/isolated/parallel/independent work | `docs/MODEL-ASSISTED-ENGINEERING.md` §5 |
| CL-005 | **No PF token for internal callers (interim)**; one shared instance per service per environment | `docs/PF-API-SERVICE-OR-SERVER.md` |
| CL-006 | **Gate 1 must embed the latest Gate 1.5 findings + dispositions; approval is invalid while any BLOCKER/MAJOR is PENDING** | `scripts/dev/gate1_check.py` + `docs/REVIEW-GATES-LIFECYCLE.md` |
| CL-007 | **Default 1.5/2.5 to the direct provider call; use a sub-agent only when investigation is needed; pre-check recurring blocker classes before 1.5** | `config/architect-review.json` (`design_checklist`) + `architect_review.py checklist` |
| CL-008 | **Inject review learnings at DESIGN/GROOMING time, not only at Gate 1.5; the design must address the guardrails before review** | `scripts/dev/design_guardrails.py` + design-mode review prompt + `docs/REVIEW-GATES-LIFECYCLE.md` |

> **Machine capture:** `scripts/dev/review_learnings.py --propose` emits rows carrying a
> `<!-- sig:<digest> -->` marker so `--check` sees the recurring finding as captured. Manually-authored
> process rules (e.g. CL-006/007) have no single review digest and are intentionally not tracked by
> `--check`.

## 7. One line
**Every correction → a durable rule + an enforcement point; if it isn't enforced somewhere machine-readable, it
isn't fixed.**
