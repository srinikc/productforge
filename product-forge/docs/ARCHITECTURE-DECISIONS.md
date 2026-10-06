# Architecture Decision Register (ADR)

**Item:** BI-PF-0392 (Epic A / A0) · Owner: architecture · Format: MADR-style.
The register is the governance anchor for Epic A. ADRs are **immutable once accepted**; supersede with a new
ADR. Individual ADRs may later be split into `docs/adr/NNNN-*.md` (the index here stays the source of truth).

## How to add an ADR
1. Copy the template below into a new section.
2. Fill Context · Drivers · Options · Decision Outcome · Consequences · Confirmation.
3. Add a row to the index. Status: Proposed → Accepted → (Deprecated | Superseded by ADR-NNNN).

## Index
| ADR | Title | Status | Date |
|---|---|---|---|
| [ADR-0001](#adr-0001-go-first-compiled-delivery) | Go-first compiled delivery (one source, many editions) | Accepted | 2026-10-06 |

## Template
```markdown
# ADR-NNNN: <title>
**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXXX
**Date:** YYYY-MM-DD   **Deciders:** <roles>   **Related:** <backlog item(s)>
## Context and Problem Statement
## Decision Drivers
## Considered Options
## Decision Outcome
**Chosen option:** "…" because …
### Consequences
**Positive:** …  **Negative:** …  **Risks:** …
### Confirmation
```

---

# ADR-0001: Go-first compiled delivery (one source, many editions)

**Status:** Accepted
**Date:** 2026-10-06
**Deciders:** Product/Architecture
**Related:** BI-PF-0387 (delivery baseline), BI-PF-0388, Epic A (BI-PF-0390), plan `docs/PF-TARGET-ARCHITECTURE-AND-IP-PLAN.md`

## Context and Problem Statement
PF's platform is 100% Python (`core/packaging.py` ships `source_dir`; 632 tracked `.py`). Deploying it to a
customer/enterprise/OEM environment exposes readable source → IP/reverse-engineering risk and loss of recurring
value. We need one codebase that ships safely across SaaS/Community/Professional/Enterprise/OEM without forks.

## Decision Drivers
- IP protection on customer-deployed editions.
- One source, many editions (no per-edition codebases).
- Keep development velocity (Python for internal/AI/build-time).
- Deterministic, reproducible, signed, air-gap-friendly delivery.

## Considered Options
1. Keep all Python; ship source (status quo) — no protection.
2. Full Python→Go rewrite — huge, AI ecosystem gap, big-bang risk.
3. **Go-first for new + existing compiled + migrate by value** (strangler).
4. SaaS-only (never ship) — not viable for on-prem/OEM demand.

## Decision Outcome
**Chosen option:** Option 3.
- **One source, one implementation per feature.** New **shipped/sensitive** features → **Go**; new
  build-time/AI/experimental → Python. **Existing Python → compiled** (Nuitka). High-value legacy → migrated to
  Go **by value** later.
- **Build compiles, never translates** (`go build` / Nuitka). **No raw `.py` in any customer package.**
- **SaaS runs the source; customer ships the compiled artifact + license.**
- A full rewrite is a **non-goal/aspiration**; compiled Python is the fallback for the low-value remainder.

### Consequences
**Positive:** strong protection where it matters; no forks; velocity retained for internal/AI; edition-flexible.
**Negative:** polyglot baseline (Python + Go) + Go↔Python contract; compiled-Python is partial protection;
Go ramp cost. *We accept these; mitigated by contract-first + value-driven migration.*
**Risks:** build complexity for compiled artifacts → mitigated by a CI build matrix + no-raw-source release gate.

### Confirmation
- A shipped package contains **no readable `.py`** (release gate).
- New shipped features land in Go; `work_pull`/`scheduler` unaffected.
- ADR-0001 is referenced by Epic A items and `BI-PF-0387`.
