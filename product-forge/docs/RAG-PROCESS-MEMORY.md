# RAG & Process Memory (SSOT)

Make **decisions / learning / corrections** durable and **retrievable**, so the model reads the right prior
context at task start — behaviour changes deterministically without touching weights. Also covers **durable vs
working memory**. Binding with `docs/MODEL-ASSISTED-ENGINEERING.md`, `docs/CORRECTION-LEDGER.md`,
`docs/GLOSSARY.md`, EDP-21 (memory: FTS/pgvector).

## 1. Goal
The model should not rely on its (short-lived, drift-prone) context window to remember how we work. Instead it
**retrieves** the relevant decisions/rules/corrections from an indexed store and gets them injected at the point
of work.

## 2. Sources to index
- Backlog items: `decisions[]`, AC, dispositions, status, epic/parent links.
- **ADRs** (`docs/ARCHITECTURE-DECISIONS.md`) and SSOT docs (this set, review-gates, API/service, EOS).
- **Correction ledger** entries (`docs/CORRECTION-LEDGER.md`).
- Review **findings + dispositions** (`engineering/reviews/*.json` + item `review_dispositions`).
- **Glossary** entries (`docs/GLOSSARY.md`); RCCA entries; incident/defect records; commit/PR messages.

## 3. Pipeline
`capture → normalize → chunk (small, self-contained) → embed → index (vector + metadata) → retrieve (at triggers)
→ inject (ranked, budgeted) into the prompt`.

## 4. Metadata schema (per chunk)
`scope` · `type` (decision | rule | correction | adr | glossary | finding) · `item_id` · `date` · `tags` ·
`status` (**active | superseded**) · `owner` · `source`.

## 5. Retrieval triggers
Gate 1 (design/take-up) · before writing code · Gate 1.5/2.5 (review) · any re-scope. Query by
`item_id + scope + type` + recency + topical similarity.

## 6. Authority & supersession (critical)
- **Ordering:** SSOT/ADR > decision ledger > backlog item; recency breaks ties.
- Decisions are **versioned**; a revision **supersedes** the old one (`status=superseded`, retained not deleted).
- **Contradiction detection:** if a proposed change contradicts an **active** entry → **STOP** and surface to HIL
  (enforces "no silent divergence").

## 7. Freshness & evaluation
Re-validate periodically; decay/flag stale; never inject superseded items as authority. Measure *did injected
context prevent a known drift?*; a **recurring correction** means the ledger/rule isn't working.

## 8. Staging (pragmatic)
1. **No-embeddings first** — heuristic retrieval by `item_id + scope + type + recency` (cheap, immediate value).
2. **Then vector RAG** — semantic retrieval + metadata filters. Natural home: the EDP memory layer
   (EDP-21 planned FTS/pgvector; `MemoryRepository`).

## 9. Durable vs working memory
- **Working memory** = the model's context window (fast, short-lived, expensive, drift-prone).
- **Durable memory** = persisted session/project memory that can be **re-injected** into fresh contexts.
- **Patterns:** rolling summarization/compaction; **handoff notes** (where we are / decided / next); a project
  memory store; **fresh session per bounded unit** (pick up via durable memory instead of a huge window).
- **Caveat:** durable memory can be stale/wrong → same **supersession + validation** discipline; never authority
  over SSOT/ADR.

## 10. One line
**Index decisions/learning/corrections with metadata + supersession; retrieve and inject them at every task
start and gate; keep working memory small and durable memory authoritative-but-validated.**
