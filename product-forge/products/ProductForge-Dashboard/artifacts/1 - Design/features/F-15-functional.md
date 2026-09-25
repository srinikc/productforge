## F-15: Deployment Options
**Feature ID:** F-15
**Summary:** F-15 covers *where and how* Product Forge itself is deployed and operated. It defines the deployment-target catalog, the topology and sizing profiles an operator can choose from, the provisioning/bootstrap path for each option, the configuration and secret-management contract, upgrade/rollback, scaling, high availability, backup/restore, observability wiring, network/TLS and identity wiring, data-residency placement, air-gapped/offline delivery, entitlement binding, drift detection, multi-environment promotion, hardening profiles, cost estimation, and decommissioning. It owns the platform's *operational envelope*: the set of supported deployment options, the guarantees each option makes, the capabilities each option exposes, and the machine-readable manifest that describes a running installation. F-15 publishes a stable deployment API of deployment targets, deployment records, configuration revisions, health/parity reports, and upgrade plans.

**Boundary note:** F-15 does not own project/run records (F-1), model-tier definitions (F-2), stage orchestration, run execution, or HIL gate definitions (F-3), portfolio membership and roll-up semantics (F-4), multi-project run-group structure (F-5), manual command semantics or the confirmation/audit surface (F-6), Auto Mode policy and ledger (F-7), the dashboard UX component system (F-8), conversational reasoning and grounding (F-9), voice I/O (F-10), the mobile companion experience (F-11), test definitions, test runs and quality-gate verdicts (F-12), the public API contract, versioning lifecycle, credentials, quotas, or the request/response envelope (F-13), or API reuse/extension analysis (F-14). F-15 governs the runtime environment those features execute inside; it never reads or mutates their domain state except to report deployment-level health and capability parity.

### Requirements

#### Functional Requirements
| ID | Requirement | Description |
|---|---|---|
| FR-304 | Deployment target catalog | Maintain a registry of supported deployment targets (single-node local, container-orchestrated self-hosted, managed cloud service, hybrid split-plane, air-gapped/offline). Each target publishes a machine-readable descriptor: supported topologies, required services, minimum resource envelope, supported capability set, and support tier. Descriptors are versioned and immutable once published; a new descriptor version supersedes rather than rewrites the old one. |
| FR-305 | Deployment profile selection | Allow an operator to select a deployment profile at install time and to create named custom profiles derived from a supported target. A profile records target, topology, sizing, region/zone placement, storage class, and feature-flag defaults. Profiles are versioned and a deployment record pins exactly one profile revision. |
| FR-306 | Topology planning and pre-flight feasibility check | Compute the concrete topology (service count, replica counts, data-store topology, network boundaries) implied by a profile, and validate it against the operator's declared capacity envelope before any resource is provisioned. Emit an itemized, actionable feasibility report that names every unmet requirement. |
| FR-307 | Provisioning and bootstrap | Provision a deployment from a validated plan: create or attach infrastructure according to the target, install the platform components, initialize the platform data stores, seed the first administrator identity, and mark the deployment `ready`. Provisioning is resumable and idempotent; re-running an interrupted provision must not create duplicate resources. |
| FR-308 | Configuration management | Store deployment configuration as a versioned, diffable document set (platform settings, component settings, feature-flag defaults). Every change produces a new immutable configuration revision with author, timestamp, reason, and previous revision pointer. Deployments always declare the configuration revision they are currently running. |
| FR-309 | Secrets and credential injection | Accept secrets (database credentials, signing keys, external service credentials, identity-provider client secrets) by reference rather than by value, resolving them from an operator-declared secret store or file-mounted source. Secrets never appear in configuration revisions, logs, audit records, or API responses. |
| FR-310 | Configuration validation and dry-run | Validate a proposed configuration revision against the target's schema, against resource constraints, and against cross-field invariants (for example, HA requires a quorum-capable data store) before it can be applied. Provide a dry-run that reports the concrete change plan and predicted impact without mutating the deployment. |
| FR-311 | Upgrade planning and execution | Compute an upgrade path from the running platform version and configuration to a requested version, including ordered migration steps, required compatibility checks, and estimated downtime per step. Execute the plan with per-step progress, checkpoints, and automatic halt on a failed pre-condition. |
| FR-312 | Rollback and downgrade handling | Roll a failed or unwanted upgrade back to the last known-good deployment state (platform version plus configuration revision) where the target supports it. Where downgrade is not data-safe, refuse before mutating and state exactly which migration makes it irreversible. |
| FR-313 | Scaling configuration | Allow declared scale changes (replica counts, worker concurrency, data-store capacity tier, storage growth) as configuration revisions. Distinguish scale-out that is safe to apply online from scale changes that require a maintenance window, and report which applies. |
| FR-314 | High availability and failover configuration | Support declaring multi-replica, multi-zone, or multi-region availability posture per component. Report each component's actual achieved redundancy versus its declared posture, and flag components that are declared HA but running single-instance. |
| FR-315 | Backup, restore, and disaster recovery | Configure backup scope, schedule, retention, and destination per deployment; record the resulting recovery point objective and recovery time objective; support restore into the same deployment or into a new deployment from a backup. Restore operations are auditable and require explicit confirmation. |
| FR-316 | Health, readiness, and deployment status reporting | Publish a per-deployment status document covering component health, configuration revision in effect, achieved capability set, degraded modes, and outstanding drift. Status is queryable at any time and is the authoritative source for "is this installation healthy". |
| FR-317 | Capability parity reporting | Report which platform capabilities are available, degraded, or unavailable on a given deployment target, so that operators and other features know what a specific installation can actually do (for example, no outbound network ⇒ voice/cloud-model features degraded). Parity is derived from the target descriptor plus measured runtime state. |
| FR-318 | Network, ingress, and TLS configuration | Declare ingress endpoints, hostnames, TLS certificate sources, and internal network boundaries as configuration. Validate that declared endpoints resolve and that certificate material is present and not expired before applying. |
| FR-319 | Identity provider wiring | Configure the deployment's identity integration (local administrator, external identity provider, or federation) including issuer, client reference, claim mapping, and provisioning mode, without storing client secrets in configuration documents (see FR-309). |
| FR-320 | Data residency and placement rules | Declare allowed regions/zones for data storage and processing per deployment, and validate that declared placement matches the target's actual resource placement. Report any component whose actual placement violates the declared rule. |
| FR-321 | Offline and air-gapped delivery | Support deployment into environments with no outbound network access: provide signed offline artifact bundles, offline-compatible upgrade paths, and a local artifact source. In this mode the deployment must operate without contacting external services and must report which capabilities are consequently unavailable. |
| FR-322 | Entitlement and license binding | Bind the deployment to an entitlement record (tier, seat/usage limits, expiry), expose current usage against those limits, and surface an entitlement-state condition when the entitlement is missing, expired, or exceeded. Entitlement state never blocks read access to already-recorded platform data. |
| FR-323 | Drift detection and reconciliation | Continuously compare the live deployment's actual resource and configuration state against its declared profile revision and configuration revision. Report drift as an itemized finding with severity, and offer reconciliation that converges live state to declared state (or, where the live change is intentional, adoption of the live state into a new configuration revision). |
| FR-324 | Multi-environment promotion | Model the operator's environments (for example, development, staging, production) as related deployment records, and support promoting a validated configuration revision and platform version from one environment to the next with a diff preview and per-environment overrides. Promotion never copies secrets. |
| FR-325 | Hardening and compliance profiles | Offer named hardening profiles (baseline, regulated, restricted-network) that constrain configuration choices — for example, disabling plaintext transport, requiring external identity, forcing audit retention minimums — and validate any configuration revision against the active profile. |
| FR-326 | Resource sizing and cost estimation | Estimate the resource footprint and, where pricing information is available for the target, the recurrent cost of a proposed profile or scale change, expressed as a range with the assumptions listed. Estimation never mutates the deployment and is clearly marked as an estimate. |
| FR-327 | Teardown and decommissioning | Decommission a deployment: drain or stop platform services in dependency order, produce a final export or backup where requested, revoke deployment-bound credentials, and record the terminal state. Teardown requires explicit typed confirmation and is irreversible once the final export completes. |
| FR-328 | Deployment change audit trail | Record every deployment-relevant action (provision, configure, upgrade, roll back, scale, restore, reconcile, decommission) in an append-only, queryable trail with actor, timestamp, prior and resulting versions, and outcome. The trail is never rewritten, including by later upgrades. |

#### Non-Functional Requirements
| ID | Requirement | Target | Measurement |
|---|---|---|---|
| NFR-190 | Provisioning time | Single-node local target reaches `ready` in ≤ 15 minutes on the reference hardware envelope; orchestrated target in ≤ 45 minutes excluding infrastructure creation. | Timed end-to-end provisioning run, recorded in the deployment audit trail. |
| NFR-191 | Zero-downtime upgrade | Supported minor upgrades on HA topologies complete with no failed read requests and no more than 1% failed write requests over the upgrade window. | Error-rate comparison across the upgrade window versus the preceding baseline window. |
| NFR-192 | Horizontal scalability | Platform control-plane components scale to at least 10 worker replicas without config changes beyond replica count; measured throughput scales at ≥ 70% efficiency at 4× replicas. | Load test at 1×, 2×, 4× replica counts. |
| NFR-193 | Availability posture | HA-configured deployments sustain 99.9% monthly availability of the control plane; single-node targets are explicitly documented as best-effort (no availability SLO). | Monthly uptime measurement from the health endpoint series. |
| NFR-194 | Secret handling | 100% of secrets resolved from a secret store or mounted file; zero secrets present in configuration revisions, logs, audit records, or API responses. | Automated secret-scanning over configuration revisions, logs, and API responses in CI. |
| NFR-195 | Supply-chain integrity | 100% of distributed artifacts are signed and verified at install and upgrade; unsigned or signature-mismatched artifacts are refused. | Signature verification gate in the install/upgrade pipeline. |
| NFR-196 | Data residency compliance | Declared residency rules are verified against actual placement on every drift-detection cycle; violations surface within one cycle. | Drift report inspection against declared rules. |
| NFR-197 | Cross-target portability | A configuration revision valid on one supported target validates (possibly with documented target-specific overrides) on every other supported target, or fails with a named, actionable reason. | Portability validation across the full supported target matrix. |
| NFR-198 | Rollback recovery time | Rollback to the last known-good deployment state completes within 30 minutes for supported downgrade paths. | Timed rollback rehearsal per release. |
| NFR-199 | Backup recovery point | Configurable recovery point objective down to ≤ 1 hour for the platform data stores; backup completion is verifiable and reported. | Backup ledger check: last successful backup age versus configured RPO. |
| NFR-200 | Status freshness | Deployment health and drift status reflects reality within 60 seconds of a change. | Timestamp comparison between the change event and the next status read. |
| NFR-201 | Minimum footprint | Single-node target runs within the documented minimum resource envelope (CPU, memory, disk) for the declared feature set. | Resource measurement on the reference hardware envelope. |
| NFR-202 | Offline operation | Air-gapped deployments complete install, run, and upgrade using only the offline artifact bundle, with zero outbound network calls attempted. | Network-egress audit during an air-gapped install and upgrade. |
| NFR-203 | Configuration application safety | Any configuration revision that fails validation is rejected before any component is mutated; partial application is impossible for validated atomic revisions. | Test suite asserting no partial mutation on rejection. |
| NFR-204 | Deployment audit retention | Deployment change-audit records are retained for the deployment's lifetime and are immutable; retention is never shorter than the active hardening profile's minimum. | Audit-trail integrity check on every release. |

#### User Stories
| ID | Story |
|---|---|
| US-180 | As a **platform operator**, I want to see the catalog of supported deployment targets with their required services and capability sets, so that I can choose an option that matches my infrastructure before committing to anything. |
| US-181 | As a **platform operator**, I want to define a named deployment profile capturing target, topology, sizing, and region, so that I can reuse a validated configuration across environments. |
| US-182 | As a **platform operator**, I want a feasibility check to tell me exactly what my chosen topology needs before provisioning starts, so that I do not discover missing capacity halfway through an install. |
| US-183 | As a **platform operator**, I want provisioning to be resumable and idempotent, so that a network failure mid-install does not leave me with duplicated or orphaned resources. |
| US-184 | As a **platform operator**, I want every configuration change to produce a new immutable revision with author and reason, so that I can always answer "what changed, when, and why". |
| US-185 | As a **security engineer**, I want secrets referenced rather than stored, so that configuration documents, logs, and API responses can be shared without leaking credentials. |
| US-186 | As a **platform operator**, I want to dry-run a configuration change and see its concrete impact, so that I can apply it confidently during a low-traffic window. |
| US-187 | As a **platform operator**, I want an upgrade to be planned as ordered, checkable steps with downtime estimates, so that I can schedule it and abort safely if a pre-condition fails. |
| US-188 | As a **platform operator**, I want rollback to be refused *before* mutation when it is not data-safe, so that I never discover irreversibility after the fact. |
| US-189 | As a **platform operator**, I want to declare HA posture per component and see the achieved redundancy, so that I know which parts of my installation are genuinely redundant. |
| US-190 | As a **platform operator**, I want to configure backup scope, schedule, and retention and see the resulting RPO/RTO, so that I can defend my recovery posture to auditors. |
| US-191 | As a **support engineer**, I want a single deployment status document covering health, configuration revision, capabilities, and drift, so that I can diagnose an installation without guessing. |
| US-192 | As a **platform operator**, I want to deploy into an air-gapped environment using a signed offline bundle, so that regulated or isolated networks can run the platform. |
| US-193 | As a **platform operator**, I want drift to be reported as itemized findings with reconciliation or adoption options, so that manual hotfixes are either reverted deliberately or recorded deliberately. |
| US-194 | As a **platform operator**, I want to promote a validated configuration revision from staging to production with a diff preview, so that environments stay consistent without hand-copying settings or secrets. |

### Behaviour

- A deployment record is created in state `planned` from a profile revision; it becomes `provisioning` when a validated plan is executed, `ready` when all components report healthy, `degraded` when one or more components are unhealthy but the control plane is serving, and `decommissioned` terminally.
- Every deployment always references exactly one **profile revision** and exactly one **configuration revision**. Both are immutable. To change either, a new revision is created and applied; the deployment's pointer moves.
- Configuration application is atomic per revision: a revision either applies fully or is rejected before any component mutates. There is no partial-application state.
- Secrets are resolved at apply time and at component start time. A secret that cannot be resolved causes the application to fail with a named error and leaves the previous configuration revision in effect.
- Upgrades are computed as a plan, not executed as a single command. Each plan step declares its pre-conditions, its post-conditions, and whether it is reversible. Execution halts on the first failed pre-condition and retains the checkpointed state for rollback.
- Drift detection runs on a fixed cadence and on demand. Findings are classified as `cosmetic`, `material`, or `unsafe`. Reconciliation never auto-applies `unsafe` findings; it requires explicit operator acknowledgement.
- Capability parity is computed from the target descriptor intersected with measured runtime state. Unavailable capabilities are reported as names, not as silent absences, so other features can degrade knowingly.
- Air-gapped deployments set a persistent platform-level flag that suppresses all outbound calls; components that require outbound access report themselves `unavailable` rather than retrying indefinitely.
- Promotion between environments carries profile and configuration revisions plus the platform version, and explicitly never carries secret material; the target environment resolves its own secrets.

### Business Rules

BR-1. Every supported deployment target must publish a descriptor; a target with no descriptor cannot be selected.
BR-2. A deployment must always have a resolvable configuration revision; a deployment with no valid configuration revision is `degraded`, never `ready`.
BR-3. Secrets must never be persisted in configuration revisions, audit records, logs, or API responses — including in error messages and dry-run output.
BR-4. A configuration revision that fails schema, constraint, or cross-field validation is rejected as a whole. Partial application is forbidden.
BR-5. Rollback is only offered for migration steps explicitly marked reversible. Where a step is irreversible, the upgrade plan must state this and require explicit acknowledgement before execution begins.
BR-6. Air-gapped mode forbids outbound network access. Any component that attempts outbound access in this mode is a defect, not a configuration choice.
BR-7. Deployment audit records are append-only for the lifetime of the deployment, including across upgrades and rollbacks.
BR-8. Capability degradation must be *declared* in the parity report before it is *experienced* by an operator wherever the target descriptor predicts it.
BR-9. Hardening profile constraints override operator configuration choices; a revision that violates the active profile is rejected with the violated rule named.
BR-10. Cross-environment promotion never transfers secrets, and never overwrites a target environment's identity-provider wiring without explicit per-environment override.
BR-11. Teardown requires typed confirmation and a completed or explicitly-waived final export before infrastructure is destroyed.
BR-12. Entitlement exhaustion never blocks read access to already-recorded platform data; it may block new write-class operations per the entitlement terms.

### Validation

V-1. **Profile validation** — target identifier must exist in the target catalog; topology must be one the target descriptor supports; sizing values must be within the descriptor's stated minimum and maximum.
V-2. **Configuration schema validation** — every key must match the target's configuration schema; unknown keys are rejected, not ignored.
V-3. **Cross-field invariants** — HA posture requires a quorum-capable data store; multi-region placement requires residency rules declaring every named region; external identity requires a resolvable issuer and claim mapping.
V-4. **Secret reference validation** — each secret reference must resolve to a non-empty value in the declared secret source at apply time; references are validated by resolution, never by inlining.
V-5. **Network and TLS validation** — declared hostnames must resolve, certificate material must be present, parseable, and not within the configured expiry warning window.
V-6. **Upgrade path validation** — the requested platform version must be reachable from the running version through a defined migration path; skipping an unsupported intermediate version is rejected with the required intermediate listed.
V-7. **Residency validation** — every declared placement rule must be satisfiable by the target's actual placement capability.
V-8. **Hardening profile validation** — a revision that weakens a constraint enforced by the active hardening profile is rejected and the violated rule is named in the error.
V-9. **Scale validation** — replica counts and capacity tiers must be within descriptor-supported ranges; reductions that would drop below the data store's quorum minimum are rejected.
V-10. **Entitlement validation** — a deployment must resolve an entitlement record; a missing entitlement yields a named entitlement condition and does not prevent provisioning but is surfaced prominently in status.

### Edge Cases

EC-1. **Provisioning interrupted by network partition mid-install** — resuming must detect already-created resources and attach to them rather than recreating, and must report which resources were adopted.
EC-2. **Configuration revision applied while an upgrade is in flight** — rejected with a named conflict; configuration changes are refused during an active upgrade execution.
EC-3. **Secret rotated in the secret store while the deployment runs** — components observe the new value on next resolution; the deployment remains `ready` and the rotation is recorded in the audit trail without a configuration revision change.
EC-4. **Certificate expires during a running deployment** — status reports a `certificate_expiring` condition before expiry and `tls_invalid` after; ingress is not silently downgraded to plaintext.
EC-5. **Drift where the live state is the intentional fix** — reconciliation offers *adoption*: the live state becomes a new configuration revision with the drift finding recorded as its reason, rather than being reverted.
EC-6. **Rollback requested after data migration completed** — refused before mutation with the specific migration named as irreversible.
EC-7. **Air-gapped upgrade with a bundle missing a required artifact** — refused at bundle verification, before any component is stopped.
EC-8. **Entitlement expires mid-operation** — in-flight operations complete; new write-class operations are refused with a named entitlement error; read access continues.
EC-9. **Multi-region deployment where one region becomes unreachable** — status reports per-region reachability; the deployment enters `degraded`, not `ready`, and the unreachable region is named.
EC-10. **Two operators apply conflicting configuration revisions concurrently** — the first to apply wins; the second is rejected on revision-pointer mismatch and must rebase onto the new revision.
EC-11. **Scale-out beyond the target's supported maximum** — rejected with the supported maximum named and the required target upgrade stated.
EC-12. **Teardown requested while runs are executing** — refused until runs are drained or the operator explicitly confirms forced teardown; forced teardown is recorded as such.
EC-13. **Profile revision referenced by a deployment is deprecated** — existing deployments continue on the deprecated revision; new deployments may not select it, and an upgrade advisory is surfaced.
EC-14. **Second administrator seeded during re-bootstrap** — the bootstrap step is idempotent and refuses to create a duplicate first administrator.

### Error Handling

EH-1. **Validation failures** return a structured, itemized error naming each violated rule, the offending field, and the expected condition. No component is mutated.
EH-2. **Provisioning failure** halts at the failed step, records the failure in the deployment audit trail, leaves the deployment in `provisioning` with the failed step marked, and offers resume or teardown. It never leaves the deployment falsely `ready`.
EH-3. **Configuration apply failure** (for example, an unresolvable secret) leaves the previous configuration revision in effect, reports the failure, and records the attempt in the audit trail as failed.
EH-4. **Upgrade step failure** halts the plan at the failed step, retains checkpoints, and offers rollback to the last checkpoint or to the last known-good state, with the reversibility of each option stated.
EH-5. **Rollback refusal** returns a named irreversible-migration error before any mutation; it is never a post-hoc failure.
EH-6. **Secret resolution failure** returns a named error referencing the secret's *logical name* only — never its value, path contents, or any derivative.
EH-7. **Drift reconciliation failure** leaves the live deployment untouched on the failing item, applies the successful items, and reports the per-item outcome; reconciliation is not all-or-nothing by default.
EH-8. **Air-gap egress attempt** is blocked and recorded as a platform defect condition with the attempting component named.
EH-9. **Entitlement failure** returns a named entitlement condition distinguishing `missing`, `expired`, and `limit_exceeded`.
EH-10. **Target descriptor missing or unsupported** returns an error naming the target and pointing at the catalog of supported targets.
EH-11. **Concurrent modification conflict** returns a revision-mismatch error carrying the current revision pointer so the caller can rebase.
EH-12. **Teardown failure mid-drain** stops at the failed component, records the terminal-but-incomplete state, and lists the components already stopped so an operator can finish manually.

### Acceptance Criteria

AC-1. The target catalog lists every supported deployment target with a machine-readable descriptor containing topology, required services, minimum resource envelope, capability set, and support tier (FR-304).
AC-2. A custom profile can be created from a supported target and pinned by a deployment record; profile revisions are immutable (FR-305).
AC-3. A feasibility check produces an itemized report and blocks provisioning when any requirement is unmet, with no resources created (FR-306).
AC-4. Resuming an interrupted provision completes successfully without creating duplicate resources, and the adopted resources are listed (FR-307, EC-1).
AC-5. Every configuration change produces a new revision with author, timestamp, reason, and previous revision pointer; the deployment's in-effect revision is queryable (FR-308).
AC-6. Secret scanning of configuration revisions, logs, audit records, and API responses returns zero findings in CI (FR-309, NFR-194).
AC-7. Dry-run of a configuration revision reports the change plan and predicted impact and mutates nothing (FR-310).
AC-8. An upgrade plan lists ordered steps, pre-conditions, reversibility, and estimated downtime per step; execution halts on a failed pre-condition (FR-311, EH-4).
AC-9. Rollback to the last known-good state succeeds within the NFR-198 target for a supported downgrade path, and is refused before mutation for an irreversible path (FR-312, NFR-198, EC-6).
AC-10. Declared HA posture per component is compared against achieved redundancy and declared-HA-but-single-instance components are flagged (FR-314, US-189).
AC-11. Backup configuration yields computed RPO/RTO, and restore into the same or a new deployment is possible and auditable (FR-315, NFR-199).
AC-12. Deployment status returns component health, in-effect configuration revision, achieved capability set, degraded modes, and outstanding drift, refreshed within 60 seconds of a change (FR-316, NFR-200).
AC-13. Capability parity is derived per deployment and names unavailable capabilities rather than omitting them (FR-317, BR-8).
AC-14. Air-gapped install and upgrade complete using only the offline bundle with zero outbound calls recorded (FR-321, NFR-202, BR-6).
AC-15. Drift detection reports itemized findings classified by severity, and offers both reconciliation and adoption; reconciliation never auto-applies `unsafe` findings (FR-323, EC-5).
AC-16. Promotion from one environment to another shows a diff preview, carries profile/configuration revisions and platform version, and transfers no secrets (FR-324, BR-10).
AC-17. A configuration revision violating the active hardening profile is rejected with the violated rule named (FR-325, BR-9, V-8).
AC-18. Cost and sizing estimation returns a range with assumptions listed and mutates nothing (FR-326).
AC-19. Teardown requires typed confirmation, produces a final export or an explicit waiver, and records a terminal state (FR-327, BR-11).
AC-20. Every deployment action appears in an append-only audit trail with actor, timestamp, prior and resulting versions, and outcome; the trail is unmodified by a subsequent upgrade (FR-328, BR-7, NFR-204).
AC-21. A configuration revision that fails validation is rejected in full with no component mutated (NFR-203, BR-4, EH-3).
AC-22. All distributed artifacts are signature-verified at install and upgrade; mismatches are refused (NFR-195).
AC-23. Portability validation across the supported target matrix either passes or fails with a named, actionable reason (NFR-197).
AC-24. Every user story US-180 through US-194 maps to at least one verified acceptance criterion above.

### API Behaviour

The deployment API is a resource-oriented surface. All collection responses are paginated; all mutating requests accept an idempotency key; all reads return the deployment's current revision pointers; all errors use a uniform error envelope naming the violated rule.

| ID | Operation | Method & Path | Behaviour |
|---|---|---|---|
| API-1 | List deployment targets | `GET /deployment-targets` | Returns target descriptors (id, version, supported topologies, required services, resource envelope, capability set, support tier). Filters: `topology`, `capability`, `support_tier`. Read-only. |
| API-2 | Get deployment target | `GET /deployment-targets/{targetId}/versions/{version}` | Returns one immutable descriptor version. 404 names the target and version. |
| API-3 | List deployment profiles | `GET /deployment-profiles` | Returns profile summaries with their current revision pointer. |
| API-4 | Create deployment profile | `POST /deployment-profiles` | Creates a profile and its initial revision. Body: target id/version, topology, sizing, placement, feature-flag defaults. Validated per V-1. Returns 201 with the new profile and revision. |
| API-5 | Create profile revision | `POST /deployment-profiles/{profileId}/revisions` | Adds an immutable revision. Requires `If-Match` on the current revision pointer; mismatch returns 409 with the current pointer. |
| API-6 | List deployments | `GET /deployments` | Returns deployment summaries: state, profile revision, configuration revision, platform version, health roll-up. |
| API-7 | Create deployment (plan) | `POST /deployments` | Creates a `planned` deployment from a profile revision and an optional configuration revision. Does not provision. Returns 201. |
| API-8 | Feasibility check | `POST /deployments/{id}/feasibility-check` | Runs FR-306 validation against the declared capacity envelope. Returns an itemized report; makes no changes. |
| API-9 | Provision deployment | `POST /deployments/{id}/provision` | Starts provisioning. Idempotent by idempotency key. Returns 202 with an operation id; provisioning is a long-running operation. Re-invocation after interruption resumes (FR-307). |
| API-10 | Get deployment | `GET /deployments/{id}` | Returns state, profile revision, configuration revision, platform version, per-component health, achieved capability set, degraded modes, and outstanding drift. Fresh according to NFR-200. |
| API-11 | Get deployment status | `GET /deployments/{id}/status` | Returns the status document only (health, conditions, drift count, entitlement state). Designed for frequent polling and monitoring. |
| API-12 | Get capability parity | `GET /deployments/{id}/capabilities` | Returns available / degraded / unavailable capabilities with the reason for each non-available entry. |
| API-13 | List configuration revisions | `GET /deployments/{id}/configurations` | Returns configuration revisions (author, timestamp, reason, previous pointer). Secret values are never included. |
| API-14 | Create configuration revision | `POST /deployments/{id}/configurations` | Creates a new immutable configuration revision. Body contains secret *references* only. Validated per V-2 through V-4, V-8. 422 on violation with itemized rules. |
| API-15 | Dry-run configuration revision | `POST /deployments/{id}/configurations/{revId}/dry-run` | Returns the concrete change plan and predicted impact. Makes no changes (FR-310). |
| API-16 | Apply configuration revision | `POST /deployments/{id}/configurations/{revId}/apply` | Moves the deployment's configuration pointer. Atomic per NFR-203. Refused with 409 during an active upgrade (EC-2). |
| API-17 | Plan upgrade | `POST /deployments/{id}/upgrade-plans` | Computes an upgrade plan to a requested platform version. Returns ordered steps, pre-conditions, reversibility, downtime estimate. Refuses unsupported version skips per V-6. |
| API-18 | Execute upgrade plan | `POST /deployments/{id}/upgrade-plans/{planId}/execute` | Executes the plan. Long-running operation. Halts on the first failed pre-condition (EH-4). |
| API-19 | Roll back | `POST /deployments/{id}/rollback` | Rolls back to the last known-good state. Refused before mutation with a named irreversible migration where applicable (EH-5). |
| API-20 | Scale deployment | `POST /deployments/{id}/scale` | Applies a scale change as a configuration revision, reporting whether it is online-safe or requires a maintenance window (FR-313). |
| API-21 | Backup configuration | `PUT /deployments/{id}/backup-policy` | Sets scope, schedule, retention, destination; returns computed RPO/RTO. |
| API-22 | Restore | `POST /deployments/{id}/restores` | Restores from a named backup into this deployment or a new one. Requires explicit confirmation; audited (FR-315). |
| API-23 | Drift report | `GET /deployments/{id}/drift` | Returns itemized findings with severity classes `cosmetic` / `material` / `unsafe`. |
| API-24 | Reconcile drift | `POST /deployments/{id}/drift/reconcile` | Applies reconciliation per item. Refuses to auto-apply `unsafe` findings; supports per-item `adopt` to convert live state into a new configuration revision (EC-5, EH-7). |
| API-25 | Promote configuration | `POST /environments/{fromId}/promote` | Promotes profile/configuration revisions and platform version to a target environment with a diff preview. Secrets are never copied (BR-10). |
| API-26 | Estimate sizing and cost | `POST /deployments/{id}/estimate` | Returns a resource and cost range with assumptions. Read-only, clearly marked as an estimate (FR-326). |
| API-27 | Decommission | `DELETE /deployments/{id}` | Requires typed confirmation and a completed or waived final export. Drains in dependency order; records a terminal state; irreversible after final export (FR-327). |
| API-28 | Deployment audit trail | `GET /deployments/{id}/audit` | Returns the append-only trail (actor, timestamp, action, prior and resulting versions, outcome). Read-only; never modifiable through the API (FR-328, BR-7). |
| API-29 | Environment list | `GET /environments` | Returns environments as related deployment records for promotion targeting. |
| API-30 | Entitlement state | `GET /deployments/{id}/entitlement` | Returns tier, limits, current usage, and state (`ok` / `missing` / `expired` / `limit_exceeded`). Read-class access is never blocked by entitlement state (BR-12). |

**Cross-cutting API rules:** every mutating call accepts `Idempotency-Key`; every revision-pointer mutation requires `If-Match`; every long-running operation (`provision`, `execute upgrade plan`, `rollback`, `restore`, `decommission`) returns an operation id resolvable through the platform's standard long-running-operation pattern owned by F-13; every error response names the violated rule (for example `V-3`, `BR-9`) and the offending field, and never contains secret material (EH-6).

### Priority

**Must-have (first release):** FR-304, FR-305, FR-306, FR-307, FR-308, FR-309, FR-310, FR-311, FR-312, FR-316, FR-323, FR-328; NFR-190, NFR-193, NFR-194, NFR-195, NFR-200, NFR-203, NFR-204; API-1 through API-19, API-23, API-24, API-28.

**Should-have:** FR-313, FR-314, FR-315, FR-317, FR-318, FR-319, FR-321, FR-322, FR-324, FR-327; NFR-191, NFR-192, NFR-196, NFR-197, NFR-198, NFR-199, NFR-201; API-20 through API-22, API-25, API-27, API-29, API-30.

**Nice-to-have:** FR-320, FR-325, FR-326; NFR-202; API-26.

**Open questions for the USER (not to be decided by Design):**
- OQ-1. Which deployment targets must the first release actually support, and which may be catalogued as "planned" only? The target set changes the provisioning surface materially.
- OQ-2. Is air-gapped/offline deployment (FR-321) required in the first release, or is it required only for a subsequent release? This determines whether the offline bundle pipeline is in scope now.
- OQ-3. Is multi-region placement (EC-9, FR-320) required, or is multi-zone within a single region sufficient?
- OQ-4. What is the required deployment audit retention period where no hardening profile is active?
- OQ-5. Should entitlement exhaustion (BR-12) block new run initiation, and if so on whose authority — this touches F-3 and F-6 boundaries and needs an explicit product decision.
