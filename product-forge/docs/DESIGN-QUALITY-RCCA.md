# Design Quality RCCA — why designs omit wiring/proof and how to prevent it

Status: binding guidance for every backlog item
Scope: all scopes (`product_forge` and generated products)
Related: `AGENTS.md`, `docs/REVIEW-GATES-LIFECYCLE.md`, `templates/DESIGN-PACK.md`
Canonical reviewer: `docs/AGENT-ROLE-CONTRACTS.md` → Architect reviewer (read-only; Gate 1.5 and Gate 2.5).
`docs/review.md` is retired and is never approval evidence.

## 1. Problem statement

Designs repeatedly described capabilities (quotas, degradation, SLOs, benchmarks) without specifying:

- the runtime entrypoint and exact call site;
- the real adapter/contract used in production;
- the failing end-to-end test that proves the capability;
- the evidence required to close each acceptance criterion;
- what was explicitly not wired.

The result: unit tests passed, dry-runs passed, reviews approved deltas, but the feature was dead code or misleading at runtime.

## 2. 5 Whys (general)

1. **Why did the design omit wiring?**  
   It was written as a capability/architecture narrative, not as an executable implementation contract.
2. **Why was a narrative accepted?**  
   The design checklist required sections (requirements, contracts, tests), but not a call-site map or a failing runtime proof.
3. **Why did tests not catch it?**  
   Tests were written after code, targeting helpers with fakes/dry-runs, not the shipped path.
4. **Why were those tests accepted as proof?**  
   “Tests pass” was treated as equivalent to “runtime works”; evidence was optional.
5. **Why did review miss it?**  
   Reviews were often delta reviews. A delta can miss cumulative missing wiring; full-candidate review came late.

## 3. Root causes

- **Abstraction bias:** design stops at interfaces and names, not ownership/call sites.
- **Happy-path bias:** failure/degradation paths are described but not wired.
- **Proof-after-code:** tests are written to match implementation instead of failing first.
- **Mock acceptance:** fakes/dry-runs accepted where production uses real adapters.
- **No evidence standard:** ACTIONED findings do not require a test/evidence path.
- **Scope breadth:** large items are decomposed into modules, not end-to-end behaviors.
- **Review mode:** delta-only review hides missing integration.
- **Reward mismatch:** green checks and completed tickets are treated as success, not working software.

## 4. Corrective actions

### 4.1 Design must be executable

Every capability in `design_pack` must include:

| Field | Required |
|---|---|
| Runtime entrypoint | process/service/CLI/API |
| Exact call site | file + function/route |
| Real adapter | production path, not mock |
| Contract | inputs/outputs/errors/timeouts |
| Failure behavior | fail-closed/fallback/rollback |
| Observability | metrics/logs/alerts |
| Proof test | failing test/demo first |
| Evidence | command/output/artifact path |
| Non-goals | explicitly not wired |

A design without these is not Gate 1 ready.

### 4.2 Proof-first implementation

1. Write a failing end-to-end test/demo against the real path.
2. Show the failure.
3. Implement the smallest change.
4. Re-run the same test; show pass.
5. Only then add helper/unit tests.

### 4.3 Evidence-based dispositions

- `ACTIONED` requires a test name, command, or artifact path.
- `ACCEPTED`/`DEFERRED` follow the disposition policy.
- No evidence = `PENDING`.
- No self-approval.

### 4.4 Review mode

- At least one **full-candidate** review per item before Gate 2.
- Delta reviews only for the fix batch; design deltas review changed design fields only.
- A full review must verify wiring/call sites, not just changed lines.
- Repeated design reviews must not re-review unchanged design sections.

### 4.5 Scope and stop rules

- One end-to-end capability per item.
- If a review finds a blocker: stop, re-scope.
- If a review finds >2 majors: stop, split.
- Process/governance changes are separate from feature items.

### 4.6 Design delta reviews

- A design delta reviews **only changed design fields**, with the full design as context.
- Verify prior findings first; do not reopen them without new evidence.
- Do not report new findings outside the delta; tag them `[OUT_OF_SCOPE]`.
- Any AC, contract, test, control, or evidence change must update the matching design rows in the same delta.
- Record `base_sha`, `head_sha`, `design_sha`, changed fields, and `review_scope: delta`.
- Design deltas do not consume the full-review budget; HIL decides after the agreed delta pass.

### 4.7 General design-pack checks (from repeated review findings)

Every design pack must answer these before it is Gate-1 ready:

| Area | Required in the design pack |
|---|---|
| Runtime proof | Each AC has runtime acceptance evidence, not only unit/config tests. |
| Adapter wiring | Concrete DB/object/cache/queue adapter files and call sites are in scope. |
| Per-store enforcement | Per-store quota config/schema and integration tests exist; not just a shared helper. |
| Freshness/dead-man | Per-store benchmark freshness metric and alert exist, including bootstrap/missing-baseline alerts. |
| Repeatability | Warmup, iteration count, concurrency, deterministic seed/data, variance/tolerance, host drift, and outlier policy are quantified. |
| Generated config | SLO rules/dashboard are generated once and validated with promtool/Grafana schema + drift checks in CI. |
| Entrypoint ownership | One production path is named; secondary/tooling paths are marked non-production and cannot bypass controls. |
| Tenant/RLS plans | EXPLAIN samples include representative tenant/RLS shapes, not only static SQL without tenant parameters. |
| Config lifecycle | SLO/quota/degradation config has versioning, audit, approval, and startup schema validation. |
| Artifact provenance | Baselines/EXPLAIN artifacts have stable naming, checksums, immutability/retention, and access control. |
| Labels | Metric labels use a bounded vocabulary; no tenant, timestamp, path, or free-text labels. |
| Alerts | Rules declare severity, owner/routing, `for` duration, and runbook URL. |
| Skip policy | CI/release evidence forbids `--allow-skip` unless explicitly waived. |
| Audit tests | Audit/retention/access-control settings have schema or integration tests. |
| Naming | Artifact paths use stable benchmark/version keys, not work-item-coupled names. |
| Tooling scope | Tooling-only files are marked as such and excluded from runtime AC claims. |
| Per-store evidence | AC proof names per-store evidence; prose is not proof. |

### 4.8 Base + inferred area completeness

The design spec is **base + inferred areas**, not a fixed template and not a blank form.

- Base areas are always required: security, tenant/RLS, observability, rollback, evidence.
- Inferred areas come from the work item: DB, API, UI, business workflow, customer journey, industry domain, voice/multimodal, storage, DR, virtualization, etc.
- Every area in `design_pack.design_areas` must be:
  - `APPLICABLE` with filled sections and evidence, or
  - `N/A` with a concrete reason and no hidden requirement.
- Blank, placeholder, or unexplained `N/A` is invalid.
- The LLM must expand the design to its full scope; it may not simply mark areas `N/A` to finish.
- Multi-area items merge all inferred areas; conflicts fail closed.
- Unknown/ambiguous areas are recorded as open questions and require HIL confirmation.
- The rendered design pack lists every area and its status/reason/sections/evidence.

## 5. Prevention checklist (Gate 0/1/1.5)

Before approving a design:

- [ ] Every AC has a runtime entrypoint and call site.
- [ ] Every capability names its real adapter and owner file.
- [ ] Every AC has a failing test/demo plan against the real path.
- [ ] Fakes/dry-runs are explicitly marked as non-proof.
- [ ] Failure/degradation/rollback paths are wired, not just described.
- [ ] Evidence path is named.
- [ ] Non-goals are explicit.
- [ ] No process/governance work is bundled.
- [ ] Per-store adapter call sites and quota config/schema are scoped.
- [ ] Runtime acceptance evidence exists for every AC, including freshness/dead-man alerts.
- [ ] Generated config has promtool/Grafana schema + drift checks and config lifecycle/audit.
- [ ] Baseline/EXPLAIN artifacts have provenance, stable naming, retention, and access control.
- [ ] Labels are bounded; alerts declare severity/owner/runbook; skip flags are forbidden in CI.
- [ ] Scope fits one reviewable item; otherwise split.

## 6. Hard rule

> If the design cannot state where the code is called, how a failing test proves it, and what evidence closes the AC, the design is not approved.

This applies to every item in every scope. The model is not the only variable; the standard must be enforced by the gate and by evidence.
