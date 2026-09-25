## F-14: API Reuse and Extension Analysis

**Feature ID:** F-14
**Summary:** F-14 defines the analysis layer that sits beside the API surface owned by F-13. It continuously inventories the versioned, machine-readable API contracts published by F-13, matches them against registered consumer demand, and answers one question for every proposed capability: *can an existing operation be reused as-is, extended additively, versioned, or must something genuinely new be introduced?* F-14 owns the inventory snapshot, the demand registry, the matching and gap-detection engine, the reuse/extension classification, the duplication and overlap findings, the per-area coverage score, the review/decision record, and the published reuse guidance. It is **read-only** against authoritative contracts and never mutates, deprecates, or publishes an API on another feature's behalf.

**Boundary note:** F-14 does not own the API contract, its versioning lifecycle, client credentials, rate limits, or the request/response envelope (F-13), project/run records (F-1), model-tier definitions (F-2), run and stage execution or HIL gate definitions (F-3), portfolio membership and roll-up semantics (F-4), multi-project run-group structure (F-5), manual command semantics (F-6), Auto Mode policy/ledger (F-7), the dashboard component system (F-8), companion surfaces (F-9, F-10, F-11), or the test domain and quality gates (F-12). F-14 consumes their published API contracts and surfaces as *inputs* and emits findings, scores, and guidance as *outputs* for humans and gated automation.

---

### Requirements

#### Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-289 | **Contract inventory ingestion** — Ingest the versioned, machine-readable API contracts published by F-13 (operations, resources, schemas, scopes, versions, deprecation markers) and store an immutable, revision-pinned inventory snapshot for each ingestion. | must-have |
| FR-290 | **Consumer demand registry** — Register a demand item describing a needed capability: originating consumer (dashboard surface of F-1…F-12, SDK/CLI client, external integrator, agent), capability description, justification, priority, and target major version. | must-have |
| FR-291 | **Reuse candidate matching** — For each demand item, match against the inventory and return a ranked list of reuse candidates with a similarity rationale, matched operation identifiers, and a confidence value. | must-have |
| FR-292 | **Gap detection** — Identify demand items for which no existing operation adequately satisfies the capability, and classify each gap as missing field, missing filter/sort, missing operation on an existing resource, or entirely new resource/capability. | must-have |
| FR-293 | **Extension classification** — Assign every finding exactly one disposition: reuse-as-is, reuse-with-additive-extension, new operation on existing resource, new API version required, or consolidation/retirement candidate. | must-have |
| FR-294 | **Backward-compatibility assessment** — Evaluate each proposed extension against the contract's compatibility rules and flag anything non-additive (removed/renamed fields, changed types, narrowed enums, changed status codes, tightened scopes) as requiring a major version. | must-have |
| FR-295 | **Duplication and overlap detection** — Detect redundant or near-duplicate operations across versions, namespaces, and feature areas, and rank consolidation opportunities by overlap severity and consumer footprint. | should-have |
| FR-296 | **Reuse coverage scoring** — Compute a reuse coverage score per feature area, per consumer, and per contract version (share of satisfied demand met by existing operations versus newly introduced surface). | should-have |
| FR-297 | **Recommendation report generation** — Produce a durable, versioned, revision-pinned report containing findings, evidence citations, dispositions, rationale, and recommendations, addressable by a stable identifier. | must-have |
| FR-298 | **Review and decision workflow** — Allow an authorized reviewer to accept a reuse recommendation, approve an extension proposal, request more information, or reject a finding; record every decision immutably with reviewer identity, timestamp, and rationale. | must-have |
| FR-299 | **Analysis run lifecycle** — Support creation, scheduling, execution, scoping (by feature area, contract version, consumer, or demand item), cancellation, and re-execution of analysis runs, with all inputs pinned to explicit contract revisions. | must-have |
| FR-300 | **Change-impact re-analysis** — Subscribe to F-13 contract change events, determine which prior analyses a change invalidates, re-run the affected scope, and mark superseded reports as stale rather than deleting them. | should-have |
| FR-301 | **Report export and sharing** — Export reports and findings in machine-readable and human-readable forms, with stable per-finding identifiers suitable for linking from reviews, tickets, and documentation. | should-have |
| FR-302 | **Reuse guidance publication** — Publish per-feature-area guidance ("prefer these operations; extend these additively; do not add new surface in this area") that API authors and agents can query before proposing new surface. | should-have |
| FR-303 | **Analysis audit trail** — Retain an immutable history of ingestion snapshots, analysis runs, rule-set versions, findings, score computations, and reviewer decisions, queryable by run, operation, consumer, or date range. | must-have |

#### Non-Functional Requirements

| ID | Requirement | Target / Measurement |
|---|---|---|
| NFR-179 | **Full-coverage analysis performance** — A complete analysis across the full registered surface (all modules, workflows, stages, agent cards, and stores exposed through the contract) completes within a bounded wall-clock window. | Full-coverage run ≤ 15 minutes at the platform's registered scale; measured as p95 run duration in the analysis telemetry surface. |
| NFR-180 | **Incremental re-analysis latency** — Re-analysis triggered by a single contract change event becomes available promptly. | Change-event-to-fresh-report ≤ 60 seconds for a single-operation scope; measured from event receipt to report publication. |
| NFR-181 | **Scalability and availability** — Concurrent analysis runs across independent scopes do not corrupt or cross-contaminate snapshots; the analysis surface remains available during contract ingestion. | ≥ 10 concurrent scoped runs supported; ≥ 99.5% monthly availability of the query/report read surface; zero snapshot cross-contamination in concurrency tests. |
| NFR-182 | **Determinism and reproducibility** — Identical pinned inputs (same contract revision, same rule-set version, same demand set) yield an identical finding set and identical dispositions. | Byte-identical finding set across two runs on the same pinned inputs; verified by reproducibility test. |
| NFR-183 | **Security and least privilege** — F-14 holds read-only access to contracts, enforces the caller's authorization scope on every read, and never emits credentials, tokens, or secret material into reports or findings. | Read-only contract scope verified by policy audit; zero secret-pattern matches in generated artifacts; unauthorized scope returns a denial rather than redacted data. |
| NFR-184 | **Data residency and retention** — Analysis snapshots, reports, and audit records are stored in the same residency boundary as the source contract and honor the configured retention policy. | Residency configuration honored per deployment; retention independently configurable for snapshots, reports, and audit records; deletion honors retention without destroying required audit history. |
| NFR-185 | **Auditability** — Every state change of a finding, report, or decision is attributable, ordered, and immutable. | 100% of decisions carry actor, timestamp, prior and new state; no in-place mutation of a published report. |
| NFR-186 | **Explainability** — Every disposition and score is traceable to the evidence (operation identifiers, contract revision, rule identifier, demand item) that produced it. | 100% of findings expose at least one evidence citation and the rule identifier applied; unsupported findings are reported as "insufficient evidence" rather than guessed. |
| NFR-187 | **Observability** — Ingestion, run, matching, and decision events emit structured telemetry sufficient to diagnose degraded matching quality. | Structured logs and metrics for ingestion, run lifecycle, finding counts by disposition, and match-confidence distribution; alert on analysis failure or stale-flag backlog. |
| NFR-188 | **Accessible and localized presentation** — Any human-facing analysis surface complies with the accessibility and internationalization contract of the shared dashboard component system (F-8). | WCAG 2.1 AA for analysis views; locale-aware date/number formatting; no layout breakage under text expansion. |
| NFR-189 | **Deployment and environment parity** — The same analysis semantics apply in sandbox and production environments; no production deployment path allows F-14 to write to a live contract. | Rule-set version identified in every report; sandbox and production produce equivalent findings for the same pinned inputs; write capability absent from the production role. |

#### User Stories

| ID | Story |
|---|---|
| US-169 | As a **platform engineer**, I want to see which existing operations already satisfy a capability I need, so that I do not design and ship redundant API surface. |
| US-170 | As an **architect**, I want a ranked list of genuine capability gaps, so that I can sequence real API work instead of duplicate work. |
| US-171 | As an **API owner**, I want duplication and overlap findings for my namespace, so that I can consolidate before consumers depend on both shapes. |
| US-172 | As a **reviewer**, I want to approve or reject an extension proposal with recorded rationale, so that the decision is defensible later. |
| US-173 | As an **external integrator**, I want reuse guidance I can trust, so that I build against stable operations rather than churn. |
| US-174 | As a **product owner**, I want a reuse coverage score per feature area, so that I can see where the platform keeps reinventing itself. |
| US-175 | As a **security reviewer**, I want to see scope and authorization overlap across operations, so that I can catch privilege sprawl early. |
| US-176 | As a **release manager**, I want every proposed extension classified as additive or breaking, so that I know whether a major version is required. |
| US-177 | As a **CI automation**, I want to query reuse guidance for a proposed operation before merge, so that I can block redundant surface automatically. |
| US-178 | As an **auditor**, I want the full history of runs, inputs, and decisions, so that I can reconstruct why surface exists. |
| US-179 | As a **newly onboarded engineer**, I want per-area reuse guidance, so that I follow existing conventions instead of guessing. |

---

### Behaviour

1. **Ingestion.** On each contract revision published by F-13, F-14 creates a new immutable inventory snapshot: operations, resources, request/response schemas, parameters, auth scopes, versions, deprecation markers, and stability tier. Snapshots are additive — earlier snapshots are retained for reproducibility (FR-289, NFR-182).
2. **Demand capture.** A consumer registers a demand item with a capability statement, justification, priority, target major version, and originating surface (FR-290). Demand items persist until explicitly closed with a disposition.
3. **Matching.** For each open demand item the engine searches the pinned snapshot for candidate operations, scores each candidate on structural fit (resource, verb, parameters, response shape) and semantic fit (capability description versus operation description), and returns a ranked candidate list with a rationale per candidate (FR-291, NFR-186).
4. **Gap and extension classification.** Demand items with no candidate above the acceptance threshold are classified as gaps. Gaps and partially-matching demands are then classified into exactly one disposition (FR-292, FR-293). Every disposition carries the evidence that produced it.
5. **Compatibility gating.** Before a disposition of "reuse-with-additive-extension" can be accepted, the proposed change is evaluated against compatibility rules. Non-additive changes are reclassified as requiring a new major version, never silently allowed (FR-294).
6. **Duplication sweep.** Independently of demand, the engine sweeps the snapshot for overlapping operations, ranks consolidations by severity, and attaches the consumers currently observed against each overlapping operation (FR-295).
7. **Scoring.** Coverage scores are computed for the scoped set and attached to the report; scores are derived from findings, never entered manually (FR-296).
8. **Report publication.** A run publishes one report: scope, pinned inputs, rule-set version, findings, dispositions, scores, and evidence. Reports are immutable; correction happens by superseding, not editing (FR-297, NFR-185).
9. **Review.** A reviewer acts on individual findings. Decisions are appended to the report's decision log; a rejected finding remains visible as rejected with rationale (FR-298).
10. **Re-analysis.** When F-13 publishes a change, affected scopes are re-analysed and the previously published report is flagged stale with a pointer to its successor (FR-300).
11. **Guidance.** Accepted decisions roll up into per-area guidance that authors and CI can query before proposing new surface (FR-302, US-177).

---

### Business Rules

| ID | Rule |
|---|---|
| BR-1 | F-14 is read-only against every contract owned by F-13. It may recommend deprecation or consolidation but can never perform it. |
| BR-2 | Every finding must resolve to exactly one disposition from the closed set: reuse-as-is, reuse-with-additive-extension, new-operation-on-existing-resource, new-major-version, consolidation-or-retirement-candidate. |
| BR-3 | An additively-classified extension may not remove, rename, retype, or narrow any published element; doing so forces the new-major-version disposition. |
| BR-4 | A reuse-as-is disposition requires at least one candidate whose confidence meets the acceptance threshold; below threshold, the finding must be reported as a gap or as insufficient evidence. |
| BR-5 | Published reports are immutable. Any correction produces a new report that supersedes the prior one, and the prior one is retained. |
| BR-6 | A demand item cannot be closed except by a recorded reviewer decision or by ingestion of a contract revision that satisfies it. |
| BR-7 | Guidance is advisory for human authors and blocking only where an external consumer chooses to enforce it; F-14 does not itself block a merge or a release. |
| BR-8 | Findings never assert behaviour that is not evidenced in a contract revision; unobserved state is reported as unobserved. |
| BR-9 | Security-scope overlap findings are reported at the operation-and-scope level only; no credential, token, or secret value is ever included in a finding, report, or export. |
| BR-10 | An analysis run whose inputs cannot be fully pinned (missing contract revision or missing rule-set version) must fail rather than produce partial findings. |

---

### Validation

| ID | Validation |
|---|---|
| V-1 | A demand item requires: capability statement (non-empty), originating consumer (existing identifier), priority (must/should/could), and target major version (existing version or "unassigned"). |
| V-2 | An analysis run request requires a scope selector; a scope that resolves to zero operations is rejected as empty scope rather than producing an empty report. |
| V-3 | A contract revision is only ingestible if it is machine-readable, carries a version identifier, and declares its stability tier; otherwise ingestion is rejected with the specific defect. |
| V-4 | A non-additive extension proposal must name the specific breaking element (removed/renamed field, changed type, narrowed enum, changed status code, tightened scope) to be accepted for assessment. |
| V-5 | A reviewer decision requires a rationale of substance (not a bare acceptance) and an actor with authority over the finding's feature area. |
| V-6 | Report exports must resolve every cited operation identifier to an existing snapshot entry; dangling citations block export. |
| V-7 | Guidance publication requires at least one accepted decision per published rule; unreviewed findings are excluded from guidance. |

---

### Edge Cases

| ID | Edge case | Handling |
|---|---|---|
| EC-1 | Two operations are semantically identical but live in different feature areas and different major versions. | Report as consolidation candidate across versions, with the newer version as the reuse target and the older version's consumer footprint attached as migration risk. |
| EC-2 | A demand item is satisfied by an operation that is already deprecated. | Classify as reuse-then-migrate: name the deprecation successor as the preferred candidate and record a migration obligation on the demand item. |
| EC-3 | The contract revision changes mid-run. | The run continues against its pinned snapshot; a new run is queued for the new revision and the completed report is immediately flagged stale. |
| EC-4 | A demand item is worded so vaguely that matching returns many low-confidence candidates. | Report as insufficient evidence with the candidate list attached at low confidence; do not force a reuse disposition. |
| EC-5 | A proposed extension is additive in shape but widens an authorization scope. | Treated as non-additive for security review purposes and requires explicit reviewer sign-off before being classified additive. |
| EC-6 | The same capability is demanded independently by several consumers. | Findings are deduplicated into one capability finding with all originating demand items linked, while per-consumer attribution is preserved for scoring. |
| EC-7 | An operation appears in the snapshot but has no consumers and no demand. | Reported as retirement candidate with zero footprint, explicitly marked as "no observed consumers" rather than "unused". |
| EC-8 | Two analysis runs are launched on overlapping scopes simultaneously. | Runs execute independently against their own pinned snapshots; the later published report wins as current and the earlier is linked as prior. |
| EC-9 | A consumer demands a capability that deliberately exists only in the dashboard of F-8 and not in the API of F-13. | Reported as an API-parity gap, citing the dashboard surface as the evidence, with the decision on whether to expose it left to review. |
| EC-10 | Guidance and a newly published contract revision conflict. | The guidance is marked stale and the conflicting revision is surfaced on the guidance entry until a review decision restores consistency. |

---

### Error Handling

| ID | Error | Behaviour |
|---|---|---|
| EH-1 | Contract source unreachable during ingestion. | Ingestion fails atomically; the previous snapshot remains current and the failure is recorded on the ingestion log with the cause. No partial snapshot is stored. |
| EH-2 | Malformed or non-machine-readable contract revision. | Ingestion is rejected with the specific defect (missing version, unparseable schema, undeclared stability tier) and the offending revision is quarantined for inspection. |
| EH-3 | Rule-set version unavailable for a requested re-run. | The run fails with an explicit "rule set not found" outcome; F-14 does not silently fall back to a different rule set (per BR-10). |
| EH-4 | Matching engine exceeds its time budget on a very large scope. | The run reports partial-scope completion with the unprocessed scope named explicitly; no disposition is emitted for unprocessed demand items. |
| EH-5 | Reviewer lacks authority over the finding's feature area. | The decision is refused with a scope-denial outcome; the finding remains open and the attempt is recorded in the audit trail. |
| EH-6 | Report export target is unavailable. | Export fails with a retryable outcome; the report itself remains published and unchanged. |
| EH-7 | A cited operation is missing at export time. | Export is blocked and the dangling citation is named so the report can be superseded with a corrected snapshot. |
| EH-8 | Duplicate change events for one revision. | Re-analysis is idempotent per revision; repeated events produce one successor report and further duplicates are collapsed. |
| EH-9 | Credential or secret material detected in candidate text. | The finding is emitted with the material redacted and a security flag raised; the raw material is never persisted in reports or exports (per BR-9). |

---

### Acceptance Criteria

| ID | Criterion |
|---|---|
| AC-1 | Given a contract revision published by F-13, when ingestion runs, then an immutable snapshot exists that resolves every operation, schema, and scope in that revision, and the snapshot identifier is recorded on every subsequent finding that used it. |
| AC-2 | Given a registered demand item with an adequate existing operation, when analysis runs, then the report contains a reuse-as-is finding naming that operation with a confidence value and at least one evidence citation. |
| AC-3 | Given a demand item with no adequate existing operation, when analysis runs, then the report contains a gap finding classified as field, filter/sort, operation-on-existing-resource, or new resource/capability. |
| AC-4 | Given a proposed extension that removes or renames a published field, when compatibility assessment runs, then the disposition is new-major-version and the breaking element is named in the finding. |
| AC-5 | Given an additive extension that does not remove, rename, retype, or narrow anything, when compatibility assessment runs, then the disposition is reuse-with-additive-extension. |
| AC-6 | Given two overlapping operations, when the duplication sweep runs, then a consolidation finding ranks them and lists the consumers observed against each. |
| AC-7 | Given an accepted decision set, when coverage scoring runs, then scores are present per feature area, per consumer, and per contract version, and every score is derivable from the attached findings. |
| AC-8 | Given a published report, when a reviewer records a decision, then the decision is appended with actor, timestamp, prior state, new state, and rationale, and the report body itself is unchanged. |
| AC-9 | Given a contract change event, when re-analysis completes, then the predecessor report is flagged stale with a pointer to the successor, and the predecessor is still retrievable. |
| AC-10 | Given identical pinned inputs run twice, when both runs complete, then the finding sets and dispositions are identical and both reports declare the same rule-set version. |
| AC-11 | Given a caller lacking authority over a feature area, when the caller requests findings or records a decision for that area, then the request is denied rather than returning redacted data. |
| AC-12 | Given a demand item satisfied only by a deprecated operation, when analysis runs, then the finding names the deprecation successor and records the migration obligation. |
| AC-13 | Given a report export, when any cited operation identifier no longer resolves, then the export is blocked and the dangling citation is named. |
| AC-14 | Given any generated report, export, or finding, when scanned for secret patterns, then no credential, token, or secret value is present. |
| AC-15 | Given a run requested with an unpinnable input, when the run is submitted, then the run fails with an explicit cause and no report is published. |

---

### API Behaviour

F-14's own surface is published through the versioned contract owned by F-13 and follows that contract's envelope, versioning, pagination, filtering, idempotency, authorization-scope, and long-running-operation rules without redefining them. Behaviourally:

| ID | Operation behaviour |
|---|---|
| API-1 | **Snapshot ingestion** accepts a contract revision reference and returns a snapshot identifier; the operation is idempotent per revision — re-submitting the same revision returns the existing snapshot rather than creating a duplicate. |
| API-2 | **Snapshot read** returns the inventory for a snapshot identifier, paginated over operations, filterable by resource, version, stability tier, and deprecation state, with sparse fieldsets supported for large inventories. |
| API-3 | **Demand item create/read/update/close** supports partial update of description, priority, and target version; closure requires a disposition reference and is rejected without one. |
| API-4 | **Analysis run submission** accepts a scope selector, an optional rule-set version (defaulting to current), and an idempotency key; it returns a run identifier immediately and the run proceeds as a long-running operation with observable status. |
| API-5 | **Run status read** returns state, progress, pinned inputs, and — on failure — the explicit cause; a run that cannot fully pin its inputs reports a failed state and publishes nothing. |
| API-6 | **Report read** returns findings, dispositions, scores, rule-set version, and evidence citations for a report identifier; superseded and stale reports are returned with their staleness marker and successor pointer rather than being hidden. |
| API-7 | **Decision submission** accepts a finding identifier, a decision (accept reuse, approve extension, request information, reject), and a mandatory rationale; it is idempotent per finding-and-reviewer-and-decision sequence and returns the updated decision log entry. |
| API-8 | **Duplication query** returns overlapping operation groups ranked by severity, filterable by namespace or feature area. |
| API-9 | **Coverage score read** returns scores per feature area, consumer, and contract version for a given report. |
| API-10 | **Guidance query** accepts a feature area and returns published reuse rules with the accepted decisions that produced them, and flags any rule made stale by a newer contract revision. |
| API-11 | **Analysis event subscription** allows a consumer to subscribe to finding-published, disposition-changed, report-superseded, and guidance-stale events; delivery follows the subscription rules of F-13 and subscribers receive only findings within their authorization scope. |
| API-12 | **Dry-run preview** evaluates a proposed operation description or demand item against current snapshots and returns candidate reuse matches and a provisional disposition without creating a demand item or publishing a report. |
| API-13 | **Audit query** returns ingestion, run, scoring, and decision history filtered by run, operation, consumer, or date range, read-only and paginated. |

---

### Priority

**Must-have:** FR-289 (inventory ingestion), FR-290 (demand registry), FR-291 (reuse matching), FR-292 (gap detection), FR-293 (extension classification), FR-294 (compatibility assessment), FR-297 (report publication), FR-298 (review and decision), FR-299 (run lifecycle), FR-303 (audit trail); NFR-179, NFR-182, NFR-183, NFR-185, NFR-186, NFR-189.

**Should-have:** FR-295 (duplication sweep), FR-296 (coverage scoring), FR-300 (change-impact re-analysis), FR-301 (export and sharing), FR-302 (guidance publication); NFR-180, NFR-181, NFR-184, NFR-187, NFR-188.

**Nice-to-have:** Additional matching heuristics beyond structural plus semantic fit, and rich visual exploration of overlap graphs — both are enhancements to already-satisfied capabilities, not new scope.

---

### Open Questions

| ID | Question for the user |
|---|---|
| OQ-1 | Should reuse guidance be advisory only (authors and CI decide), or must some feature areas be declared *closed to new surface* so that any new operation there requires an explicit waiver? |
| OQ-2 | Should the initial inventory scope include every registered store and module exposed through the contract, or only the externally published operations? |
| OQ-3 | What confidence threshold should distinguish "reuse-as-is" from "gap" — is the default acceptable, or should the user set it per feature area? |
| OQ-4 | Should duplication findings be permitted to recommend retirement of an operation with zero observed consumers, or is retirement always a human-only judgement recorded outside F-14? |
