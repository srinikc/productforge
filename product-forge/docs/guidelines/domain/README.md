# Domain Research Guidelines

> Knowledge layer for research/analysis agents (e.g. `researcher`, `analyst`). Applies when an
> agent must ground its output in a domain rather than general knowledge.

## 1. Cite or mark — never fabricate
- Every non-obvious claim must carry a **source** or be explicitly marked `unverified` / `assumption`.
- If no live source is available, say so and list **exact queries** that would verify it.
- Never present remembered/ambiguous facts as verified.

## 2. Use the web tool
- Research agents have `http_get`. If a claim needs current facts (pricing, competitors, market
  size, standards), **call `http_get`** rather than relying on training data.
- Record what was fetched (URLs) so the result is auditable.

## 3. Structure
- Cover: **market/category → competition → positioning → trends → risks → open questions**.
- Separate **facts (sourced)** from **hypotheses (to validate)**.

## 4. Limitations
- State coverage limits (time, regions, source types) and what was **not** verified.
- Output a `needs_research` list of precise follow-up queries.

## 5. Quality bar
- Prefer primary/authoritative sources (official docs, filings, standards) over blogs/SEO pages.
- Distinguish **category** (the space) from **competitors** (named products) from **alternatives**.
