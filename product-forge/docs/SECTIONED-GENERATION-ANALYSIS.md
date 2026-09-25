# Sectioned Generation — Approach Analysis & Risks

> Approach: for agents whose artifact can exceed one LLM call's safe output, generate the
> document **one section per call** (dynamic: single when it fits, sectioned when needed),
> then **deterministically merge** and completeness-check.

## How it works
```
shared context pack (base prompt: instructions + upstream artifacts + knowledge)
  + outline (required sections, ordered)
  → call per section (base pack + running digest of prior sections)
  → deterministic merge (append in order) + completeness retry
  → (architect) one dedicated call for the tech-stack JSON block
```

## Issues that WILL arise, and mitigations
| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | **Tech-stack contradiction** — "Architecture Style" picks Go, "Tech Stack" picks Python, JSON says Rust | **High** | Generate the **decision JSON first**, put it in the shared pack for every section; forbid contradicting it |
| 2 | **Terminology/ID drift** (component names, FR-/NFR-/ADR- numbering) | High | shared pack + running **digest**; residual risk if a section invents new names |
| 3 | **Model switching mid-doc** (fallbacks) → inconsistent voice/quality | Medium | **pin** the first successful model for all sections in the run |
| 4 | **Cost/latency × N** — the full base prompt is re-sent per section | Medium | acceptable for 5–9 sections; input tokens dominate. Could trim base pack to what the section needs |
| 5 | Base pack already lists **all sections** ("write the whole doc") → conflicts with "write only X" | Medium | explicit override line ("ignore full-doc instruction; write only {section}") — done, verify |
| 6 | **Merge artifacts**: duplicate headings, no title/intro, numbering inconsistency | Medium | deterministic normalization (single title, dedupe headings); optional global intro |
| 7 | **No section spec** on an agent that truncated → `sectioned` falls back to single → truncates again → retry loop → stage FAIL | Medium | only mark spec'd agents sectioned; or provide a **generic outline** (derive from headings) |
| 8 | **Downstream parsers** must still work: FR/NFR/feature extraction, tech-stack JSON parse | High | validate on sectioned output; JSON emitted once in its own call |
| 9 | Checklist becomes **trivially satisfied** (headings guaranteed) → hides empty sections | Low | require non-empty section bodies / min length; already log empty |
| 10 | **Text-order dependencies** (Data Model needs Components; File Structure needs Components) | Medium | generate **in order** and pass digest; residual if digest too thin |
| 11 | **Parallelism lost** — sequential needed for the digest | Low | accept; or parallelize independent sections without digest (lower consistency) |
| 12 | **Rate limits amplified** (N calls) → more 429s/fallbacks on free tier | Medium | cross-provider fallbacks; keep N modest |
| 13 | Global reasoning quality drops (split analysis loses holistic optimization) | Medium | for trade-off-heavy docs, allow a short "overview" section generated first |

## Verdict
- The approach is **sound and the right general tool** for long/structured artifacts.
- Two things are **must-fix before it's production-safe**: **#1 stack-first** and **#8 downstream parsing**.
- Then **#3 model pinning** and **#7 generic outline** to avoid loops.
- Everything else is tuning.

## Recommended implementation order
1. Generate the **decision/stack JSON first**; inject into the shared pack.
2. **Pin** the model across a sectioned run.
3. **Generic outline** fallback (or restrict sectioned to spec'd agents).
4. Deterministic **merge normalization** (title, dedupe).
5. Validate **downstream parsers** (FR/NFR/features/tech-stack) on sectioned output.
6. Then enable `sectioned` for architect/design/ideation and re-run the E2E.

## Current state
- Dynamic decision + sectioned generator are **in place** (code compiles).
- Implementation currently has mitigations for #5 (override line) and #8-partial (dedicated JSON call).
- **Not yet** addressed: #1 (stack-first), #3 (model pinning), #7 (generic outline), #4/#6 tuning.

## Hardening applied (robust, no assumptions)
- **Decision:** `sectioned` is chosen **only when a known outline exists** (config
  `required_sections`). Any other agent — including one that just truncated — stays
  `single`, so it can never enter a sectioned loop it can't satisfy.
- **Generator never crashes:** the whole sectioned path is wrapped; any error falls back
  to a single call; empty result falls back to single; **never returns empty**.
- **Outline is bounded** (≤12 sections) so no runaway.
- **Architect decision JSON generated FIRST** and injected into every section prompt, so
  sections cannot contradict the chosen stack (addresses risk #1).
- **Per-section truncation** retried once with a conciseness hint.
- **Completeness retry** for any missing essential section (one pass).
- Verified decision matrix: architect/design/ideation/document → sectioned;
  validate/implement/code-review/unknown → single (even on truncation).

## Still recommended (not correctness-blocking)
- Pin the model across a sectioned run (voice consistency, risk #3).
- Deterministic merge normalization (title, duplicate headings) — risk #6.
- Trim the base pack per section to reduce input-token × N — risk #4.
