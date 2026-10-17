# Glossary / Definitions (SSOT)

Pin the meaning of terms **before** building — ambiguous vocabulary caused real rework (API/server/token). New
terms must be defined here. Binding with `AGENTS.md` (EOS) and `docs/MODEL-ASSISTED-ENGINEERING.md`.

## Architecture & services
- **API** — the **contract** (surface + schema + guards + authn/authz + envelope). **Not** the transport.
- **Transport** — how the contract is reached: HTTP (external/service-to-service) or in-process (internal). An adapter.
- **Service** — a bounded unit owning a domain/concern; exposes an API surface and may operate its data.
- **Server / service instance** — a **running instance** of a service (process on host:port).
- **PF Server / Service** — the umbrella: the set of services that serve PF's APIs **and** operate PF.
- **Control-plane service** — Python `api/` (existing Python concerns: backlog, engineering…).
- **Data-plane service** — Go EDP (`go/edpsvc`): the SoR + everything operating it.
- **Capability service** — Go (`go/capsvc`): cross-cutting Go capabilities; calls other services over HTTP.

## Calling APIs (caller classes)
- **External / remote caller** — out-of-process/host (adapters, MCP, CLI, dashboard, other services) → **HTTP + token**.
- **Internal caller** — same process → **in-process API**; **no PF token** (interim, dev anon).
- **Implementation / gates** — the router itself, precheck gates → **library call**.

## Data & ownership
- **SoR (System of Record)** — the authoritative store for a concern (single writer).
- **Single writer** — exactly one code path owns writes to a store/concern.
- **Derived / projection** — generated from the SoR; never hand-edited.

## Process gates & review
- **Gate 0** — classification/need-check (implicit in take-up).
- **Gate 1.5** — independent **design** review, **before** Gate 1.
- **Gate 1** — HIL **design approval** (reconciliation + IMPACT REVIEW + AC), informed by 1.5. No code before this.
- **Gate 2.5** — independent **delivery** review, **before** Gate 2.
- **Gate 2** — HIL **delivery approval** (diff + independent AC verification), informed by 2.5.
- **Review finding** — BLOCKER/MAJOR/MINOR/NIT from the **reviewer** (independent).
- **Disposition** — the **main thread's** response/action to a finding (PENDING | actioned | accepted | deferred | rejected).
- **Advisory vs blocking** — only objectively verifiable classes hard-block (secret/PII, data-loss, RLS bypass,
  missing migration/test, language-rule violation); the rest HIL decides.
- **AC** — Acceptance Criterion (each ≥ 40 chars), the Definition of Done.
- **api_impact** — per-item decision `needs_api` + reason (+ routes) for API-first.
- **HIL** — Human In the Loop (the authority; approves gates).
- **EOS** — Engineering Operating Standard (`docs/ENGINEERING_OPERATING_STANDARD.md`).
- **Fail-closed** — unknown/missing evidence ⇒ blocked.
- **Evidence** — verifiable, linked proof (test result, artifact, review file), not self-report.

## Model working terms
- **Drift** — expected→delivered divergence discovered late.
- **Correction ledger** — durable record of HIL corrections → rules (`docs/CORRECTION-LEDGER.md`).
- **RAG (process memory)** — retrieve + inject prior decisions/rules/corrections at task start (`docs/RAG-PROCESS-MEMORY.md`).
- **Working memory** — the model's context window (short-lived).
- **Durable memory** — persisted session/project memory re-injectable into fresh contexts.
- **Runtime LLM guardrails** — model-I/O safety (content, injection, PII, output validation) — a separate concern.
- **Go-forward (language rule)** — new shipped/sensitive logic → Go; edits to shipped Python OK; **not** a port.

## One line
**If a term can be read two ways, it is defined here first.**
