## F-16: Voice Reference Alignment

**Feature ID:** F-16

**Summary:** F-16 owns the *voice reference* domain of Product Forge: the curated, versioned, quality-scored set of reference voice profiles that the Voice Companion (F-10) resolves and uses when speaking grounded answers. It covers the full lifecycle of a reference — registration of a target voice and its locale, ingestion of source audio samples, preprocessing and normalization, phonetic/transcript alignment, speaker-embedding extraction, objective alignment scoring and pass/review/fail verdicts, composition of immutable reference-profile versions, approval and retirement workflow, binding of profiles to languages/locales and to the Voice Companion's resolution rules, drift monitoring against fresh samples, cross-sample consistency checks, search and import/export, role-gated access, an immutable audit trail, alignment settings/presets, batch alignment, failure diagnosis, preview synthesis, and completion notifications. F-16 makes no synthesis or speech-recognition decisions: it produces the correctly aligned, approved reference artifact that F-10 consumes and F-9's conversational answer is later rendered with. F-16 never mutates historical alignment records and never promotes an unapproved profile to "effective".

**Boundary note:** F-16 does not own the voice I/O contract, microphone lifecycle, streaming speech-to-text, spoken synthesis, barge-in, spoken citations, or hands-free HIL announcements (F-10); conversational reasoning, grounding and refusal policy (F-9); the manual command preview/confirmation/execution surface (F-6); run/stage execution, HIL gate definitions, or run telemetry (F-3); project/run records (F-1); model-tier definitions (F-2); portfolio membership and roll-up semantics (F-4); multi-project run-group structure (F-5); Auto Mode policy/ledger (F-7); the shared dashboard UX component system, rendering, theming and accessibility primitives (F-8); the mobile companion shell (F-11); the API contract, versioning lifecycle, envelope, credentials, or rate limits (F-13); the API reuse/extension analysis layer (F-14); deployment topologies, provisioning, backup/restore, or residency placement mechanisms (F-15); test-case/suite/gate governance (F-12). F-16 publishes a stable reference-profile resolution surface that F-10 consumes; the call-site semantics of that consumption belong to F-10.

### Requirements

#### Functional Requirements

| ID | Requirement |
|---|---|
| FR-376 | **Voice reference registry** — Register, read, list, update, archive, restore and permanently delete voice *reference* records. Each reference carries a name, description, target voice identity label, target language/locale, owner, tags, status (`draft`, `aligning`, `in-review`, `approved`, `retired`), current profile version pointer, and configuration revision. |
| FR-377 | **Reference sample ingestion** — Accept one or more source audio samples for a reference via managed upload or a platform-managed object URI. Record original filename, declared language, declared speaker, declared transcript (optional), duration, sample rate, channel count, and codec. |
| FR-378 | **Sample preprocessing and normalization** — For every ingested sample, apply deterministic preprocessing: decode to a canonical PCM form, down-mix to the configured channel count, resample to the reference's canonical sample rate, apply loudness normalization to a configured target, trim leading/trailing silence beyond a configured threshold, and remove DC offset. Every step produces a recorded, reproducible transformation. |
| FR-379 | **Phonetic / transcript alignment** — Align each preprocessed sample against its declared transcript (when present) or against an automatically produced phoneme sequence, yielding time-aligned segments with per-segment confidence. Alignment covers the full sample; uncovered audio and uncovered transcript are both reported. |
| FR-380 | **Speaker-embedding extraction** — Extract a speaker embedding from the aligned sample and record the embedding model identity and configuration revision used, so a later embedding is interpretable and comparable. |
| FR-381 | **Alignment scoring** — Compute objective alignment quality metrics per sample: alignment confidence (segment-weighted), phoneme/segment coverage, signal-to-noise estimate, clipping ratio, effective speech duration, and embedding stability across segments. |
| FR-382 | **Quality verdicts and thresholds** — Derive a per-sample verdict of `pass`, `review`, or `fail` from configurable thresholds. Verdicts are stored with the metric values and the threshold revision used, so a verdict is always reproducible. |
| FR-383 | **Reference profile composition** — Compose a candidate reference profile from one or more aligned samples. Composition has a declared strategy (single sample, best-scoring sample, or multi-sample aggregation) and records exactly which aligned sample versions contributed. |
| FR-384 | **Immutable profile versioning** — Every composition produces a new immutable profile version. Re-running alignment or re-composing never mutates a prior version; it creates a successor that points at its predecessor. |
| FR-385 | **Approval workflow** — Move a profile version through `draft → in-review → approved → retired`. Only an `approved` profile version can become a reference's *effective* version. Approval records approver, timestamp, decision note, and the verdict bundle it was approved against. |
| FR-386 | **Language / locale binding** — Bind an approved profile version to one or more languages/locales. A reference may declare a primary locale and zero or more alternates; resolution rules and conflicts across references are surfaced, not silently resolved. |
| FR-387 | **Effective-profile resolution surface** — Publish a resolution operation that, given a language/locale (and optional voice identity label and resolution hints), returns the single effective approved profile version and the reason it was selected. F-10 consumes this; F-16 does not speak, synthesize, or stream. |
| FR-388 | **Alignment re-run** — Re-run preprocessing, alignment, embedding extraction, scoring and composition for a reference when samples, transcripts, or alignment settings change, producing a new candidate profile version without altering history. |
| FR-389 | **Drift monitoring** — Periodically re-validate approved reference profiles against freshly supplied or re-sampled audio, and report drift (metric movement beyond configured tolerance) as a reviewable finding without auto-demoting the profile. |
| FR-390 | **Cross-sample consistency check** — When a reference carries multiple samples of the same target voice, compare their embeddings and metrics and report consistency findings (outliers, mixed-speaker suspicion, recording-condition divergence). |
| FR-391 | **Search, filter and browse** — Search references and profile versions by name, target voice label, locale, status, owner, tag, approval state, and verdict; filter by drift status and by effective/non-effective. |
| FR-392 | **Import and export** — Export reference and profile-version metadata (and, where policy permits, embeddings) in a documented portable format, and import it into another installation or environment with idempotent re-keying and conflict reporting. |
| FR-393 | **Role-gated access** — Enforce role-based permissions across reference registration, sample ingestion, alignment execution, approval, retirement, export, and deletion, with separation between the person who aligns and the person who approves where the configured policy requires it. |
| FR-394 | **Audit trail** — Record every state-changing action on a reference, sample, alignment run, profile version, verdict, approval, binding, or retirement as an append-only auditable event with actor, timestamp, prior value, and new value. |
| FR-395 | **Alignment settings and presets** — Provide named, versioned alignment settings presets (thresholds, canonical sample rate, normalization target, silence trim, channel policy, embedding model) that can be selected, cloned, and applied; every alignment run records the preset revision used. |
| FR-396 | **Batch alignment** — Submit many references or samples for alignment as a batch, track per-item progress and outcome, and allow partial success without failing the whole batch. |
| FR-397 | **Failure diagnosis** — For every failed or `review` sample, produce a machine-readable and human-readable diagnosis naming the failed stage, the metric that drove the verdict, and the most probable cause categories (silence-dominated, clipping, low speech duration, transcript mismatch, mixed speakers, unsupported format). |
| FR-398 | **Preview** — Produce a preview artifact for a candidate profile version that demonstrates the aligned reference (for example a re-synthesized or re-rendered sample) so a reviewer can judge before approving, without that preview becoming the effective profile. |
| FR-399 | **Retirement and supersession** — Retire a profile version while preserving its history, maintain an explicit supersession link to a successor, and refuse to treat a retired version as effective. |
| FR-400 | **Completion notifications and events** — Emit a notification and a subscribable event when an alignment run, batch, drift check, or approval completes or fails, carrying the reference id, profile version, verdict summary, and a link to the authoritative record. |

#### Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-226 | **Alignment throughput** — A single preprocessed reference sample of up to 10 minutes of speech must complete alignment, embedding extraction and scoring within 3 minutes of wall-clock time on the standard reference deployment profile. |
| NFR-227 | **Interactive latency** — Registry reads, search, filtering, verdict retrieval and effective-profile resolution must return within 500 ms at the 95th percentile for catalogs up to 10,000 references. |
| NFR-228 | **Scalability and concurrency** — Support at least 50 concurrent alignment jobs and 2,000 registered references with 20 profile versions each without degradation beyond the stated latency and throughput targets; batch submission must scale by bounded worker pools that never starve interactive reads. |
| NFR-229 | **Availability** — The reference registry and effective-profile resolution surface must be available 99.9% monthly; a failure of the alignment worker tier must not take down registry reads or resolution of already-approved profiles. |
| NFR-230 | **Durability of reference assets** — Ingested samples, preprocessed audio, embeddings, verdict bundles, profile versions and audit records must be stored with no loss across a single-node failure, and any lost artifact must be reconstructible from its recorded transformation chain. |
| NFR-231 | **Security of voice assets** — Reference audio and embeddings are biometric-adjacent personal data: encrypt at rest and in transit, restrict access by role, never include raw audio or embeddings in logs or error payloads, and sign export bundles. |
| NFR-232 | **Consent and lawful-basis handling** — Every reference must record the declared consent/lawful basis for the target voice and its samples; alignment and approval must be blocked when the required consent record is absent for the configured policy. |
| NFR-233 | **Authorization** — Every operation must be authorized against the caller's scope; cross-tenant or cross-workspace access to another owner's references must be denied by default and auditable when denied. |
| NFR-234 | **Data residency** — Reference audio, embeddings and derived artifacts must be placeable in a configured residency region and must not be replicated outside it by processing, preview, export, or notification paths. |
| NFR-235 | **Retention and deletion** — Support configurable retention per reference and per sample; permanent deletion must remove raw audio, preprocessed audio, embeddings and derived previews, while preserving a tombstone audit event that records that deletion occurred. |
| NFR-236 | **Auditability and reproducibility** — Every verdict, profile version and effective-profile resolution must be reproducible from stored inputs plus recorded settings revisions; the audit trail must be append-only and tamper-evident. |
| NFR-237 | **Deployment and environment portability** — F-16 must function without outbound internet access (air-gapped/offline), must not require a specific vendor speech service, and must expose identical behaviour across the supported deployment options described by F-15. |
| NFR-238 | **Capacity and quota management** — Enforce per-owner quotas on stored audio duration, embedding count and concurrent alignment jobs, and surface quota pressure before it blocks work. |
| NFR-239 | **Observability** — Expose metrics for alignment queue depth, job duration by stage, verdict distribution, drift findings, quota usage and failure causes, and emit structured logs and traces correlated by alignment-run id. |
| NFR-240 | **Interoperability and contract stability** — The published reference/profile/verdict/resolution contract must be machine-readable, versioned, additive-by-default, and usable through the uniform API conventions of F-13 without requiring dashboard access. |

#### User Stories

| ID | Story |
|---|---|
| US-226 | As a **voice owner**, I want to register a reference voice with its target locale, so that the companion has an authoritative voice identity to speak with. |
| US-227 | As a **voice owner**, I want to upload several source samples for a reference, so that alignment has enough audio to build a faithful profile. |
| US-228 | As a **voice owner**, I want the platform to normalize and align my samples automatically, so that I do not have to hand-edit audio before it is usable. |
| US-229 | As a **quality reviewer**, I want an objective alignment score and verdict per sample, so that I can decide whether a reference is good enough to approve. |
| US-230 | As a **quality reviewer**, I want a preview of a candidate profile before approving it, so that I can judge the voice rather than only the numbers. |
| US-231 | As a **quality reviewer**, I want to see why a sample failed alignment, so that I can fix the input instead of guessing. |
| US-232 | As an **approver**, I want an explicit approval step that records who approved which profile version, so that only intentionally-approved voices ever become effective. |
| US-233 | As a **platform operator**, I want approved profiles bound to languages and locales, so that the companion resolves the right voice for the operator's locale. |
| US-234 | As a **platform operator**, I want the effective-profile resolution to be explainable, so that I can answer "why is the companion speaking with this voice?" |
| US-235 | As an **operator**, I want to re-run alignment after I add a better sample, so that the reference improves without losing its history. |
| US-236 | As a **platform operator**, I want drift monitoring on approved profiles, so that a voice that degrades over time is surfaced for review before it surprises users. |
| US-237 | As a **compliance officer**, I want a consent/lawful-basis record attached to every reference, so that we never align or approve a voice we are not allowed to use. |
| US-238 | As a **compliance officer**, I want an immutable audit trail and residency controls, so that I can prove what happened to each voice asset and where it stayed. |
| US-239 | As an **automation engineer**, I want to import/export references and drive alignment through the API, so that I can manage voices as code across environments. |
| US-240 | As an **administrator**, I want role-gated control and quota enforcement over voice assets, so that a single team cannot exhaust capacity or approve its own voice without review. |

### Behaviour

1. **Registration.** Creating a reference produces a `draft` record with no samples. The reference is not resolvable and can never be effective in this state. Registration captures target voice identity label, primary locale, owner, tags, and the consent/lawful-basis record (see business rules).
2. **Sample lifecycle.** Each sample is ingested, then preprocessed, then aligned, then embedded, then scored — in that order. Each step writes its own artifact and status; a sample may be independently `ingested`, `preprocessed`, `aligned`, `scored`, `failed`, or `excluded`. Excluded samples remain visible with their exclusion reason and never contribute to a composed profile unless re-included.
3. **Alignment run.** An alignment run is the unit that ties together a set of sample versions, one settings preset revision, and the produced candidate profile version. Runs are idempotent on (reference, sample version set, preset revision): re-submitting the same identity returns the existing run rather than producing a duplicate.
4. **Composition.** A candidate profile is composed only from samples that reach `scored`. The composition strategy is recorded; multi-sample aggregation records the weighting used. A composition with zero eligible samples produces a failed run with a diagnosis, not an empty profile.
5. **Verdicts.** Each sample verdict is `pass`, `review`, or `fail`. A profile-level verdict is derived from its contributing samples (for example, composed only of `pass` samples is `pass`; any `review` contributor is at best `review`; any `fail` contributor blocks composition with that strategy). Thresholds come from the preset revision recorded on the run.
6. **Approval.** A reference's *effective* version pointer moves only through an explicit approval action on a specific profile version. Approval does not change the run's verdicts; it records the human decision separately.
7. **Binding and resolution.** Locale bindings apply to an approved profile version. Resolution returns exactly one effective profile version per locale, or an explicit "unresolved" answer naming the competing or missing references. F-16 never picks a winner silently when a locale has conflicting approved candidates.
8. **Re-run and drift.** Re-running alignment produces new sample versions, a new alignment run, and a new candidate profile version. Drift monitoring is a scheduled re-evaluation that emits a finding; it never auto-retires, auto-approves, or auto-rebinds anything.
9. **Retirement.** Retiring a profile version leaves the version readable and auditable, removes it from resolution, and requires a supersession pointer when a successor exists. Retiring the currently-effective version for a locale leaves that locale explicitly unresolved until a successor is approved.
10. **Notifications and events.** Completion events are emitted after the authoritative record is durably written, so a consumer that reacts to an event always finds the referenced record present.

### Business Rules

| ID | Rule |
|---|---|
| BR-1 | A reference must have a consent/lawful-basis record before any sample may be aligned; absence blocks alignment with a specific, itemized error. |
| BR-2 | Only a profile version in `approved` state may become effective; `draft`, `in-review`, `retired`, and failed versions are never resolvable. |
| BR-3 | Profile versions are immutable. Any change — new sample, new preset, new transcript — produces a new version that points at its predecessor. |
| BR-4 | Historical alignment runs, verdicts, and audit events are never edited or deleted except by explicit, audited retention deletion. |
| BR-5 | At most one approved profile version per (reference, locale) may be effective at a time; a second approval for the same locale requires retiring or re-binding the first. |
| BR-6 | Effective-profile resolution must be explainable: it always states the reference, profile version, locale, and selection reason. |
| BR-7 | Where policy requires separation of duties, the identity that triggered alignment or composition of a profile version may not be the identity that approves it. |
| BR-8 | Verdicts are reproducible: they are stored with the metric values and the exact settings-preset revision that produced them; re-deriving a verdict for an old run must use that stored revision. |
| BR-9 | Drift findings, consistency findings, and low-confidence verdicts are reviewable queue items; they never change effective state on their own. |
| BR-10 | Raw audio and embeddings are biometric-adjacent assets: they are excluded from logs, telemetry payloads, error bodies, and notification payloads. |
| BR-11 | Export bundles must be signed and must respect residency and consent scope; an export that would cross a residency boundary is refused, not silently redacted. |
| BR-12 | Deleting a reference permanently removes its audio, embeddings and previews but leaves an immutable tombstone audit event stating that deletion occurred. |
| BR-13 | Quotas on stored duration, embedding count and concurrent jobs are enforced before work is accepted, not after it has consumed resources. |

### Validation

| ID | Validation |
|---|---|
| V-1 | Reference name is required, non-empty, and unique within its owner/workspace scope. |
| V-2 | Primary locale must be a registered language/locale tag; alternate locales must each be registered tags. |
| V-3 | Target voice identity label is required and must be a permitted value for the configured policy. |
| V-4 | A consent/lawful-basis record reference is required before alignment is permitted (see BR-1). |
| V-5 | An ingested sample must decode successfully; unsupported codec or corrupt payload is rejected at ingestion with the detected problem. |
| V-6 | A sample must declare or be assigned a language that matches the reference's declared locale set; a mismatch is a validation warning that becomes a blocking error only when the preset requires strict locale matching. |
| V-7 | A sample must contain at least the configured minimum effective speech duration after preprocessing; shorter samples are marked `review` or `fail` per preset, never silently accepted. |
| V-8 | A declared transcript, when present, must be non-empty and must be internally consistent in language with the sample declaration. |
| V-9 | Sample rate, channel count and bit depth must be within the supported ranges of the selected preset; out-of-range inputs are rejected or converted only when the preset permits conversion. |
| V-10 | Settings presets must be internally consistent (for example, a silence-trim threshold larger than the minimum speech duration is rejected). |
| V-11 | A locale binding must reference an approved profile version; binding a non-approved version is rejected. |
| V-12 | A retirement request naming a successor must reference an existing, non-retired profile version of the same reference. |
| V-13 | Batch submissions must not exceed the configured batch size or the owner's concurrent-job quota. |
| V-14 | Import payloads must declare the format version and pass schema and signature validation before any record is written. |

### Edge Cases

| ID | Edge case |
|---|---|
| EC-1 | Silence-dominated sample: preprocessing leaves almost no speech; alignment must mark the sample `fail` with a silence-dominated diagnosis rather than producing a degenerate embedding. |
| EC-2 | Clipped or heavily distorted sample: clipping ratio above the preset threshold produces `review`/`fail` with a distortion diagnosis, and the sample is never silently included in a composed profile. |
| EC-3 | Mixed speakers in one sample: consistency check reports a mixed-speaker suspicion; composition excludes it unless the preset explicitly permits mixed-source material. |
| EC-4 | Transcript mismatch: alignment confidence falls below threshold across the sample; the run reports transcript-mismatch as the probable cause and the sample is excluded. |
| EC-5 | Multiple approved references claiming the same locale: resolution returns an explicit conflict naming both references instead of silently selecting one. |
| EC-6 | Effective profile retired with no successor: the locale is left unresolved and the companion's consumer (F-10) is expected to fall back to its own defined degradation; F-16 states the locale is unresolved. |
| EC-7 | Duplicate submission of the same alignment run: idempotency returns the existing run and does not create a second profile version. |
| EC-8 | Concurrent re-run while an approval is in progress: the approval binds to the version it was opened against; the newly produced successor does not silently inherit the in-flight approval. |
| EC-9 | Sample added after a profile version was approved: the approved version is unchanged; the new sample only affects a future successor version. |
| EC-10 | Very long sample exceeding the configured maximum duration: the sample is rejected or split according to preset policy, and the effective action is recorded. |
| EC-11 | Locale with no approved profile at all: resolution returns "unresolved — no approved reference" rather than an error, so F-10 can degrade gracefully. |
| EC-12 | Drift detected while the profile is concurrently under review: the drift finding attaches to the version under review and does not create a competing version. |
| EC-13 | Export requested for a reference whose consent scope forbids export: refusal is explicit and audited; nothing partial is produced. |
| EC-14 | Deletion requested for a reference that backs a currently-effective locale: deletion is refused until the locale is re-bound or the reference is retired through the normal workflow. |
| EC-15 | Air-gapped deployment: alignment, scoring, resolution and export must all work offline; no external speech service may be required. |

### Error Handling

| ID | Error | Handling |
|---|---|---|
| EH-1 | Missing consent/lawful basis | Reject alignment with a `consent_required` error naming the reference and the missing record; no partial artifacts are produced. |
| EH-2 | Undecodable sample | Reject at ingestion with `sample_undecodable`, including the detected codec/container problem; the reference remains usable with its other samples. |
| EH-3 | Alignment engine failure | Mark the alignment run `failed`, preserve all successfully produced artifacts, emit a completion event with the failure, and allow a re-run that reuses prior successful stages where the preset permits. |
| EH-4 | Threshold violation producing `fail` | Not an error condition of the platform — it is a stored verdict with diagnosis; it blocks composition with that strategy and is reported, not thrown. |
| EH-5 | Locale conflict at resolution | Return an `unresolved_conflict` result that names the competing references and versions; callers (for example F-10) treat this as a defined, degradable state, not an exception. |
| EH-6 | Unauthorized operation | Return an `unauthorized` error without disclosing the existence of the resource; record the denial in the audit trail. |
| EH-7 | Quota exceeded | Return `quota_exceeded` before accepting the work, naming the exceeded dimension and the current usage; queued work is not silently dropped. |
| EH-8 | Storage or durability failure during artifact write | Fail the run, do not advance the version, and ensure no partial profile version is marked resolvable; retry per the platform retry policy. |
| EH-9 | Residency violation attempt (processing, export, notification) | Refuse with `residency_violation` and audit the attempt; never silently route around the boundary. |
| EH-10 | Import schema/signature failure | Reject the whole import atomically with the failing item identified; no partial records are written. |
| EH-11 | Notification/event publish failure | Do not lose the authoritative record; retry publication and, on exhaustion, surface the undelivered event as an observable backlog item. |
| EH-12 | Deletion of a reference still in effective use | Refuse with `in_use` naming the locale bindings that must be resolved first. |

### Acceptance Criteria

| ID | Criterion |
|---|---|
| AC-1 | A newly registered reference with no samples is never resolvable and never appears as an effective profile for any locale. |
| AC-2 | Ingesting a valid sample and running alignment produces a scored sample plus a candidate profile version, with the settings-preset revision recorded on the run. |
| AC-3 | Every verdict is stored together with its metric values and preset revision, and re-deriving the verdict from those stored values yields the same verdict. |
| AC-4 | A profile version cannot become effective without an explicit approval action that records approver, timestamp, and decision note. |
| AC-5 | Approving two profile versions for the same (reference, locale) is rejected unless the earlier one is retired or re-bound. |
| AC-6 | Effective-profile resolution returns exactly one version per locale, or an explicit unresolved result naming the reason — never a silent guess. |
| AC-7 | Re-running alignment after adding a sample creates a new profile version and leaves the previously approved version byte-identical. |
| AC-8 | Drift monitoring produces a reviewable finding and never changes effective state on its own. |
| AC-9 | A failed sample reports a diagnosis naming the failed stage, the driving metric, and a probable-cause category. |
| AC-10 | Missing consent blocks alignment with a `consent_required` error and no artifacts. |
| AC-11 | Role separation, where configured, prevents the aligning identity from approving the same profile version. |
| AC-12 | Every state-changing action appears in the append-only audit trail with actor, timestamp, prior value and new value. |
| AC-13 | Raw audio and embeddings never appear in logs, telemetry, error bodies, or notification payloads. |
| AC-14 | Export of a reference whose consent scope forbids export is refused and audited, producing no partial bundle. |
| AC-15 | Permanent deletion removes audio, embeddings and previews while leaving a tombstone audit event. |
| AC-16 | All alignment, scoring, resolution and export operations complete successfully in an air-gapped environment with no external speech service. |
| AC-17 | An alignment run, batch, drift check, or approval emits a completion event only after the authoritative record is durably written. |
| AC-18 | Reference and profile data can be exported and re-imported into another environment with idempotent re-keying and an explicit conflict report. |

### API Behaviour

| ID | Endpoint / operation | Behaviour |
|---|---|---|
| API-1 | `POST /voice-references` | Create a reference. Returns the reference record with `status: draft` and a stable id. Validates name, locales, target voice label and consent reference (V-1, V-2, V-3, V-4). |
| API-2 | `GET /voice-references/{id}` and `GET /voice-references` | Read one or list, with filtering by status, locale, owner, tag, verdict, effective flag, drift status (FR-391). Supports pagination and sparse fieldsets per the F-13 envelope conventions. |
| API-3 | `PATCH /voice-references/{id}` | Update mutable reference metadata (name, description, tags, locale declarations) while preserving history; status changes flow only through the lifecycle operations below. |
| API-4 | `POST /voice-references/{id}/samples` | Ingest a sample. Returns the sample record with ingestion metadata and status `ingested`. Rejects undecodable or out-of-range input (V-5, V-9, EH-2). |
| API-5 | `GET /voice-references/{id}/samples` | List samples with per-sample status, verdict, and diagnosis summary. |
| API-6 | `POST /voice-references/{id}/alignment-runs` | Start a run. Accepts a sample-version set, a preset revision, and an optional idempotency key. Returns a run id immediately; idempotent on (reference, sample-version set, preset revision) (EC-7). |
| API-7 | `GET /voice-references/{id}/alignment-runs/{runId}` | Return run status, per-sample stage progress, produced profile version, and failure diagnosis (FR-397). |
| API-8 | `GET /voice-references/{id}/profile-versions` | List immutable profile versions with predecessor pointers, contributing sample versions, composition strategy, and verdict bundle. |
| API-9 | `GET /voice-references/{id}/profile-versions/{version}` | Return the full profile version including verdicts, metric values, and preset revision for reproducibility (BR-8). |
| API-10 | `POST /voice-references/{id}/profile-versions/{version}/preview` | Produce or fetch a preview artifact for the candidate; the preview never becomes effective (FR-398). |
| API-11 | `POST /voice-references/{id}/profile-versions/{version}/approve` | Approve a specific version, recording approver, note, and the verdict bundle. Enforces separation of duties where configured (BR-7, AC-11) and the single-effective-per-locale rule (BR-5, AC-5). |
| API-12 | `POST /voice-references/{id}/profile-versions/{version}/retire` | Retire a version with an optional supersession pointer; enforces successor validity (V-12) and leaves bound locales explicitly unresolved if no successor is effective (EC-6). |
| API-13 | `PUT /voice-reference-bindings/{locale}` | Bind an approved profile version to a locale; rejects binding a non-approved version (V-11). Conflicts across references are surfaced by resolution, not resolved here. |
| API-14 | `GET /voice-reference-resolution` | Resolve the effective approved profile for a locale (and optional voice label/hints). Returns exactly one version with a selection reason, or an explicit unresolved result (FR-387, BR-6, EH-5, EC-11). This is the surface F-10 consumes. |
| API-15 | `POST /voice-reference-drift-checks` | Schedule or trigger a drift check for an approved profile version; returns a finding record and never changes effective state (FR-389, BR-9). |
| API-16 | `POST /voice-references/{id}/alignment-batches` | Submit a batch; returns a batch id and per-item tracking, and supports partial success (FR-396, V-13). |
| API-17 | `POST /voice-references/export` and `POST /voice-references/import` | Produce a signed export bundle or consume one. Refuses on residency or consent violation (EH-9, EC-13) and rejects invalid imports atomically (V-14, EH-10). |
| API-18 | `DELETE /voice-references/{id}` | Permanently delete a reference and its audio, embeddings and previews, leaving a tombstone audit event; refuses while the reference backs an effective locale (FR-399, EH-12, AC-15). |
| API-19 | `GET /voice-references/{id}/audit-events` | Return the append-only audit trail for the reference, filterable by event type and actor (FR-394, AC-12). |
| API-20 | `POST /voice-reference-settings-presets` and `GET /voice-reference-settings-presets` | Create, clone, version and read alignment settings presets; rejects internally inconsistent presets (V-10). |

**Envelope and cross-cutting API notes:** all operations use the uniform request/response envelope, error shape, pagination, filtering, sparse fieldsets, idempotency and concurrency-control conventions owned by F-13; F-16 does not define a competing envelope. Every operation is authorized against the caller's scope (NFR-233) and every state-changing operation is audited (FR-394). Publishing the reference/profile/verdict/resolution contract as a machine-readable, versioned, additive-by-default surface (NFR-240) is delegated to the contract machinery of F-13; F-16 supplies the operations and schemas. The API is read/write for management and **read-only** for consumption: F-10 resolves and reads profiles, and never writes alignment or approval state on F-16's behalf.

### Priority

**Must-have (release-critical):** FR-376 registry, FR-377 sample ingestion, FR-378 preprocessing/normalization, FR-379 phonetic/transcript alignment, FR-380 embedding extraction, FR-381 alignment scoring, FR-382 verdicts and thresholds, FR-383 profile composition, FR-384 immutable versioning, FR-385 approval workflow, FR-386 locale binding, FR-387 effective-profile resolution surface, FR-388 alignment re-run, FR-393 role-gated access, FR-394 audit trail, FR-395 settings presets, FR-397 failure diagnosis, FR-399 retirement and supersession; NFR-226, NFR-229, NFR-230, NFR-231, NFR-232, NFR-233, NFR-234, NFR-236, NFR-240.

**Should-have:** FR-389 drift monitoring, FR-390 cross-sample consistency check, FR-391 search/filter/browse, FR-392 import/export, FR-396 batch alignment, FR-398 preview, FR-400 completion notifications and events; NFR-227, NFR-228, NFR-235, NFR-237, NFR-238, NFR-239.

**Nice-to-have:** advanced preset authoring conveniences and additional non-blocking reporting refinements on top of the above (for example richer browse analytics); no additional global IDs are introduced for these.

**Open question for the USER (not decided here):** whether F-16 should ultimately support *voice cloning / synthesis of a target speaker from the reference* as part of the alignment deliverable, or whether the aligned reference is strictly a speaker-identity/quality artifact consumed by F-10's chosen synthesis path. This spec implements the latter, non-generative interpretation (alignment, scoring, approval, resolution, preview) and does not add cloning capabilities; if generative voice cloning is required, that is a scope decision belonging to the user.
