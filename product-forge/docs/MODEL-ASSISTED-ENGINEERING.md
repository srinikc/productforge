# Model-Assisted Engineering — working with models without being at their mercy (SSOT)

How we work with LLMs so their systematic biases don't cost us late rework. **Process/operating guardrails** —
distinct from **runtime LLM guardrails** (content safety, prompt-injection, PII, output validation — a separate,
later concern). Binding with `AGENTS.md` (EOS), `docs/ENGINEERING_OPERATING_STANDARD.md`,
`docs/REVIEW-GATES-LIFECYCLE.md`, `docs/GLOSSARY.md`, `docs/CORRECTION-LEDGER.md`,
`docs/RAG-PROCESS-MEMORY.md`.

## 1. The problem
We repeatedly see **expected → delivered divergence discovered late**, costing large rework and re-litigation.
Not random, not "the model is dumb" — **systematic model bias** meeting **soft, unenforced expectations**.

## 2. Root causes (honest)
1. **Unstated expectations + silent gap-filling** — implicit expectations get filled with the most *plausible*
   interpretation instead of being surfaced and confirmed. Highest-impact cause.
2. **Local optimization / anchoring** — extend the nearest artifact / shortest path instead of "who owns this".
3. **Agreeableness / sycophancy** — "go" is taken as license to proceed rather than to pin the missing decision.
4. **Discipline gap (not knowledge gap)** — rules exist (reconciliation, route-by-kind, ADRs, gates) but are
   applied non-deterministically unless enforced.
5. **Verification optimism** — "done/green" reported from self-execution without independent verification.
6. **Context inertia over long sessions** — earlier choices become sticky; re-derivation drops; drift rises.
7. **Speed pressure** — correctness traded for shipping.
8. **Unpinned vocabulary** — the same word meant different things; we built before defining.

**Truth:** these are properties of LLMs (local token plausibility, agreeableness, anchoring, no persistent memory
of corrections). Mitigate with **structure + gates + retrieval + HIL sign-off**, not model goodwill.

## 3. Operating principle
**Do not trust the model; engineer the environment so drift is blocked or caught early.** Model self-report is
not evidence; confidence comes from **gates and artifacts**.

## 4. Process guardrails (mechanisms)
1. **Decisions-first, freeze before build** — no code until HIL signs the reconciliation + IMPACT REVIEW
   (LANGUAGE/API/AC): Gate 1. (`docs/REVIEW-GATES-LIFECYCLE.md`)
2. **Ambiguity kill-switch** — every assumption/unknown → explicit question with a default, **confirmed**. No
   silent gap-filling.
3. **Definitions first** — pin terms in `docs/GLOSSARY.md` before building; new terms must be defined there.
4. **Ownership / route-by-kind gate** — mandatory *before adding anything*: whose concern? single writer?
   register it. Mechanically enforced, so drift (e.g. responder logic in the reviewer tool) is **blocked**.
5. **Independent review (Gate 1.5 / 2.5)** — findings + **our dispositions in one view**; findings = reviewer-owned,
   response/action = **main-thread-owned**; **all dispositions non-PENDING** before Gate 2.
6. **Evidence-based, fail-closed DoD** — no "done" without verifiable evidence; unknown ⇒ blocked.
7. **Correction ledger + RCCA** — every HIL correction becomes a rule/guard. (`docs/CORRECTION-LEDGER.md`)
8. **Small bounded units; short sessions / fresh sub-agents** for decision sub-tasks.
9. **HIL decides at every gate** — the model proposes, the human approves.

## 5. Sub-agents — cost + optimization
**Mostly true for *small* tasks:** a sub-agent starts with an **empty context**, so it re-discovers files/decisions
the main thread already holds, plus spawn overhead → **more tokens/latency** for the same small decision.
**They win for:** context isolation (large scans that would bloat the main window), **parallelism/independence**,
and bounded cacheable subtasks.

**Rule:** *Don't delegate what the main thread can do with its existing context. Do delegate large, isolated,
parallel, or independence-requiring work.*

**Optimize:** tight complete brief + **exact output schema** + file:line pointers; demand a **compact structured
return**; **inject context via retrieval** (see RAG doc) so it isn't re-derived; batch; avoid nesting; set
token/time bounds; reuse the same sub-agent session for related follow-ups.

## 6. RAG & process memory, durable/session memory
See **`docs/RAG-PROCESS-MEMORY.md`** — indexing decisions/learning/corrections for retrieval at task start, plus
working-memory vs durable-memory patterns.

## 7. Can we "train" the model to work our way?
- **In-context (this session):** partly; ephemeral, drifts. Not a solution.
- **Artifacts + retrieval (do this):** high leverage — rules/checklists/ADRs/glossary + correction ledger,
  **injected at task start**. Deterministic behaviour change, no weights touched.
- **Weights-level fine-tune / RLHF:** possible but we don't own hosted base models, it's costly, risks regressions,
  and is unnecessary for most of the gain. Revisit only after the retrieval path is saturated.

## 8. Concrete PF actions
Enforce Gate 1; glossary SSOT; **ownership gate**; findings+dispositions one view (all non-PENDING before Gate 2);
correction ledger + RCCA; staged RAG process-memory; durable memory/handoff notes; sub-agent usage policy.

## 9. One line
**Don't trust the model — make correctness external (definitions, ownership, gates, evidence) and learning durable
(correction ledger + RAG retrieval); use sub-agents only for large/isolated/parallel work in short bounded sessions.**
