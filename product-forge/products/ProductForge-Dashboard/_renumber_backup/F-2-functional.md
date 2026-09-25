## F-2: Project Creation and Model Tier Management

**Feature ID:** F-2

### Requirements

#### Functional Requirements

| ID | Name | Description |
|---|---|---|
| FR-26 | Project creation wizard entry | Provide a guided, multi-step entry point to create a new pipeline project, launched from the control plane (see F-1, project lifecycle registry) and resumable across sessions. |
| FR-27 | Idea capture | Capture the seed idea for the project as free-form text, with optional structured fields (goal, target users, success signals). The idea is attached to the project draft. |
| FR-28 | Project metadata | Collect and validate the project's name, description, owner, tags, and visibility as part of creation. |
| FR-29 | Portfolio assignment at creation | Allow the operator to assign the new project to zero or one portfolio at creation time, with inline creation of a new portfolio when none exists. |
| FR-30 | Pipeline definition binding | Let the operator select a pipeline definition and a pinned pipeline version to bind at creation; if none is selected, bind the platform default definition. |
| FR-31 | Model tier selection | Allow the operator to pick a predefined model tier (e.g., economical / balanced / frontier) as the project's execution profile. |
| FR-32 | Custom tier creation | Allow the operator to create a new tier by composing models per stage (or per stage group) from the model catalog. |
| FR-33 | Provider/model catalog browsing | Provide a browsable, searchable, filterable catalog of LLM providers and their available models, with capability and constraint metadata. |
| FR-34 | Model selection from catalog | Let the operator add/remove one model per configurable scope (project default, stage, or stage group) from the catalog. |
| FR-35 | Tier composition rules | Support ordering, fallback chains, and per-scope overrides when composing a tier. |
| FR-36 | Tier validation | Validate a tier before it can be used: every required scope is covered, no unknown/retired models, constraints satisfied, fallbacks resolvable. |
| FR-37 | Tier persistence library | Persist created tiers in a reusable tier library owned by the tenant, with name, description, scope coverage, and creator. |
| FR-38 | Tier editing and cloning | Allow editing of operator-owned tiers and cloning of any accessible tier into a new editable tier. |
| FR-39 | Tier versioning | Version tiers immutably; a project bound to a tier version keeps that version, and upgrades are explicit and audited. |
| FR-40 | Cost and latency estimation preview | Show estimated cost and latency bands for the selected tier/pipeline combination before project creation is confirmed. |
| FR-41 | Creation review and confirmation | Present a final review of project metadata, pipeline binding, tier composition, and estimates, requiring explicit confirmation to create. |
| FR-42 | Draft save and resume | Auto-save creation drafts and allow explicit save, list, resume, and discard of drafts. |
| FR-43 | Template-based creation | Allow creation from a saved project template (metadata + pipeline + tier preset) to accelerate repeatable setups. |
| FR-44 | Project duplication | Duplicate an existing project's creation inputs (metadata, pipeline binding, tier) into a new draft. |
| FR-45 | Bulk project creation | Allow creating multiple projects in one operation from a list/CSV input, sharing a single pipeline binding and tier. |
| FR-46 | Tier sharing, export and import | Allow exporting a tier to a portable document and importing a tier document, with validation and provenance recorded. |
| FR-47 | Default tier policy | Support tenant/administrator default tier and allowed-tier policies that constrain which tiers a project may select. |
| FR-48 | Model/provider capability metadata | Surface capability metadata per model (context window, tool use, modality, region, retirement date) and expose it wherever models are chosen. |
| FR-49 | Creation audit trail | Record who created the project, with which pipeline version and tier version, the estimates shown, and any overrides, in the audit log. |
| FR-50 | Post-creation handoff | On successful creation, hand off to the created project's workspace and surface the initial run trigger, with the binding summary. |

#### Non-Functional Requirements

| ID | Area | Requirement |
|---|---|---|
| NFR-16 | Performance | Creation wizard first paint < 1.5s; each wizard step transition < 500ms; catalog search results < 300ms for the first page. |
| NFR-17 | Scalability / Availability | Catalog browsing must remain responsive with ≥ 5,000 models and ≥ 200 providers; catalog reads are served from cache with ≥ 99.9% monthly availability. |
| NFR-18 | Security | All creation endpoints require authenticated identity; authorization is enforced per tenant and per role; no cross-tenant tier or project data is readable. |
| NFR-19 | Secrets / Credential handling | Provider credentials are never stored in tiers or project documents; tiers reference credentials by opaque handle only. |
| NFR-20 | Data residency | Project and tier records, including estimates and audit entries, are stored in the tenant's configured region. |
| NFR-21 | Deployment / Environment | Wizard and tier library behave identically across dev/staging/prod; creation writes are idempotent and safe to retry. |
| NFR-22 | Concurrency | Concurrent edits to the same tier are detected via optimistic concurrency; conflicting saves are rejected with a resolvable error. |
| NFR-23 | Auditability | Every create/update/delete of a project draft, tier, or tier version produces an immutable audit record with actor, timestamp, and diff. |
| NFR-24 | Accessibility | Wizard is fully keyboard navigable, meets WCAG 2.1 AA contrast, and announces step changes to assistive technology. |
| NFR-25 | Data integrity | A project is never persisted with a dangling pipeline version or tier version reference; referential integrity is enforced at write time. |
| NFR-26 | Rate limiting / Quotas | Bulk creation and catalog queries are rate-limited per tenant; exceeding quota returns a clear, retryable error. |
| NFR-27 | Observability | Creation funnel steps, validation failures, and estimation latency emit metrics and structured logs without logging ideas or secrets at high verbosity. |
| NFR-28 | Browser support | Wizard supports the two most recent major versions of Chromium, Firefox, and Safari, plus current mobile Safari and Chrome. |
| NFR-29 | Disaster recovery | Tier library and project drafts are included in scheduled backups with a documented restore objective (RPO ≤ 24h, RTO ≤ 4h). |
| NFR-30 | Internationalization | Wizard copy, number formatting, and currency for cost estimates respect the operator's locale. |

#### User Stories

| ID | Story |
|---|---|
| US-16 | As an operator, I want to create a project from a seed idea so that I can start a pipeline run without hand-editing configuration. |
| US-17 | As a product lead, I want to pick a predefined model tier so that I can trade off cost and quality without choosing individual models. |
| US-18 | As an operator, I want to customize a tier for specific stages so that high-value stages can use stronger models. |
| US-19 | As an operator, I want to create a new tier from the model and provider catalog so that I can define a reusable execution profile. |
| US-20 | As a product lead, I want to browse providers and models with capability metadata so that I can choose a model that fits my needs. |
| US-21 | As a product lead, I want to see a cost and latency estimate before creating a project so that I can avoid surprises. |
| US-22 | As a product lead, I want to reuse an existing tier so that I do not reconfigure models for every project. |
| US-23 | As an operator, I want my creation draft saved so that I can resume after an interruption. |
| US-24 | As a product lead, I want to create projects from templates so that repeatable setups are fast. |
| US-25 | As an operator, I want to duplicate an existing project's configuration so that similar projects are quick to set up. |
| US-26 | As an administrator, I want to set a default/allowed tier policy so that teams stay within approved models. |
| US-27 | As an operator, I want validation before project creation so that I don't bind an unusable tier. |
| US-28 | As an auditor, I want a creation history showing tier/pipeline versions and overrides so that I can trace decisions. |
| US-29 | As an operator, I want to create multiple projects in one operation so that onboarding many projects is efficient. |
| US-30 | As a product lead, I want to import and export tiers so that profiles can be shared across environments. |

### Behaviour

- **Entry (FR-26):** The wizard opens with an empty draft bound to the requesting tenant and owner. It is a linear, resumable flow with steps: Idea → Metadata → Portfolio → Pipeline → Model Tier → Estimates → Review → Create.
- **Idea (FR-27, FR-42):** The idea is stored on the draft as text plus optional structured fields. Drafts auto-save on step change and on field blur; the operator may also save explicitly.
- **Metadata (FR-28):** Name is required; description, tags, visibility, and owner are validated on input and re-validated server-side at create.
- **Portfolio (FR-29):** The operator may select an existing portfolio, create one inline, or skip. Assigning a project to a portfolio is a single membership operation.
- **Pipeline binding (FR-30):** The wizard lists available pipeline definitions with versions. Selection pins an immutable version onto the project. Default binding is applied only if the operator accepts the default.
- **Tier selection (FR-31, FR-40):** Predefined tiers are shown with their scope coverage and last-known cost band. Selecting a tier renders the estimate preview (FR-40) alongside the chosen pipeline.
- **Custom tier (FR-32, FR-35, FR-36):** The operator composes a tier by adding models at scopes (project default, stage, stage group). Every added model references a catalog entry. Composition supports ordering and fallback chains. Validation (FR-36) runs live and blocks the Review step until it passes or an explicit, audited override is recorded.
- **Catalog (FR-33, FR-34, FR-48):** The catalog is searched/filtered by provider, capability, context window, modality, region, and retirement date. Models can be added to a tier from the catalog or a comparison view.
- **Tier library (FR-37, FR-38, FR-39, FR-46):** Custom tiers are saved into a tenant-visible library with name, description, coverage, and creator. Editing an existing tier creates a new immutable version. Export produces a portable document; import validates the document and records provenance.
- **Templates and duplication (FR-43, FR-44):** Selecting a template or duplicating a project pre-fills idea/metadata (template), pipeline binding, and tier, leaving the operator to confirm or modify.
- **Bulk creation (FR-45):** The operator supplies a list of projects sharing a pipeline binding and tier; each entry is validated and created independently, with a partial-success report.
- **Default tier policy (FR-47):** If a tenant/administrator default tier exists, it is preselected; tiers outside the allowed set are shown as disabled with the reason.
- **Review and create (FR-41, FR-49, FR-50):** The Review step shows metadata, portfolio, pipeline version, tier version + composition, estimate bands, and any overrides. Confirmation creates the project atomically, records the audit entry (FR-49), and navigates to the project workspace (FR-50).

### Business Rules

- **BR-1:** A project must always resolve to exactly one pinned pipeline version and at most one pinned tier version at creation time.
- **BR-2:** Only tiers whose versions pass validation and are within the tenant's allowed-tier policy may be bound to a project.
- **BR-3:** Editing a tier never mutates a project already bound to an earlier version; upgrades are explicit operations.
- **BR-4:** Predefined/platform tiers are read-only; they may only be cloned, never edited in place.
- **BR-5:** Provider credentials are referenced by opaque handle; a tier that cannot resolve its credential handle is invalid and cannot be used for creation.
- **BR-6:** Bulk creation treats each project as an independent transaction; one failure does not roll back others, but the batch report enumerates all outcomes.
- **BR-7:** Imported tiers carry provenance metadata (source tenant/owner/document hash) and are created as new versions in the importing tenant.
- **BR-8:** A draft is owned by its creator; other users in the tenant cannot modify another user's draft unless they hold an administrative role.
- **BR-9:** Any override of a validation or policy violation must include a recorded justification and an actor.
- **BR-10:** Estimates are informational and do not guarantee actual cost/latency; the estimate basis is recorded with the creation audit entry.

### Validation

- **V-1:** Project name — required, 1–120 characters, unique within the owner's active projects per tenant.
- **V-2:** Description — optional, ≤ 2,000 characters.
- **V-3:** Idea — required before Review; free text ≤ 20,000 characters; structured goal fields ≤ 500 characters each.
- **V-4:** Tags — up to 20 tags, each ≤ 40 characters, lowercase-normalized.
- **V-5:** Portfolio selection — must reference an existing portfolio or a valid inline creation payload.
- **V-6:** Pipeline binding — must reference an existing definition and an available, non-retired version.
- **V-7:** Tier — every model reference must resolve to a catalog entry that is not retired; every required scope must be covered; fallback chains must be acyclic and resolvable.
- **V-8:** Policy check — selected tier must be within the tenant allowed-tier set, else an override with justification is required.
- **V-9:** Credential handle — if a model requires credentials, the handle must resolve for the project's execution context.
- **V-10:** Bulk input — each entry validated independently; invalid entries are rejected without blocking valid ones and reported by row.
- **V-11:** Import document — must conform to the tier document schema and pass the same validation as live composition.

### Edge Cases

- **EC-1:** Operator starts a draft with no idea and abandons at Review; the draft is preserved and resumable, but cannot be submitted.
- **EC-2:** A model is retired between tier composition and project creation; validation surfaces the retirement and requires a replacement or fallback.
- **EC-3:** A predefined tier is deprecated after being selected but before confirmation; the wizard re-validates at submit and prompts for a replacement.
- **EC-4:** Two operators concurrently edit the same tier; the second save fails the optimistic concurrency check and must reconcile.
- **EC-5:** Portfolio is deleted between assignment and submit; the wizard re-validates and asks the operator to reassign or skip.
- **EC-6:** Provider is temporarily unavailable during catalog read; catalog serves cached data with an availability badge and disables adding unavailable models.
- **EC-7:** Bulk creation receives a partially invalid list; valid rows are created, invalid rows reported with reasons, and no partial rows remain.
- **EC-8:** Imported tier document has a schema version newer than the platform supports; import is rejected with a clear message.
- **EC-9:** Some stages have no explicit model in a custom tier; the project default applies; if neither exists, validation fails.
- **EC-10:** The pipeline definition selected has no matching stage in the tier overrides; orphan overrides are flagged, not silently ignored.
- **EC-11:** Estimate cannot be produced because a referenced model has no pricing metadata; the wizard proceeds with an "estimate unavailable" notice recorded in the audit entry.

### Error Handling

- **EH-1:** Validation errors are shown inline at the offending field, with a summary at the top of the step, and block progression to the next step.
- **EH-2:** Server-side create conflicts (duplicate name, stale version) return a resolvable error identifying the conflicting field/version.
- **EH-3:** Network/offline during wizard interaction shows a persistent banner; auto-save is queued and retried; the operator is warned if a step can't be confirmed.
- **EH-4:** Catalog service errors show a recoverable error state with retry, keeping previously selected models intact.
- **EH-5:** Concurrency conflicts on tier save return a diff and offer merge/reload, never a silent overwrite.
- **EH-6:** Policy/validation overrides require an explicit confirmation dialog with justification; cancellation aborts with the draft preserved.
- **EH-7:** Bulk creation partial failures produce a downloadable per-row report with status and reasons; the operation is idempotent on retry by row key.
- **EH-8:** Import failures identify the offending schema path/element; no partial tier is persisted.
- **EH-9:** Creation failure after confirmation leaves no partial project; the draft remains intact and the operator is returned to Review with the error.

### Acceptance Criteria

- **AC-1:** Given valid idea, metadata, pipeline, and tier inputs, when the operator confirms at Review, then exactly one project is created with the selected pipeline version, tier version, and portfolio membership, and an audit entry is written.
- **AC-2:** Given the operator selects a predefined tier, when the wizard renders the Review step, then the tier's scope coverage and estimate bands are displayed.
- **AC-3:** Given the operator composes a custom tier, when a required scope is uncovered or a model is retired, then the Review step is blocked and the specific violation is shown.
- **AC-4:** Given a tenant allowed-tier policy, when a disallowed tier is selected, then the tier is disabled unless an override with justification is provided.
- **AC-5:** Given the operator edits a tier that a project already uses, when the edit is saved, then a new immutable tier version is created and existing projects remain on their prior version.
- **AC-6:** Given a draft is auto-saved, when the operator returns in a later session, then the draft resumes at the last step with prior inputs intact.
- **AC-7:** Given a bulk creation list with some invalid rows, when the operation runs, then valid rows become projects and invalid rows are reported without affecting the valid ones.
- **AC-8:** Given a valid tier export document, when it is imported into the same tenant, then a new tier version is created with provenance recorded and passes validation.
- **AC-9:** Given a creation request is retried after a timeout, when the retry is processed, then no duplicate project is created (idempotent create).
- **AC-10:** Given the operator lacks authorization to a tier or portfolio, when they attempt to reference it, then the reference is rejected with an authorization error and nothing is persisted.
- **AC-11:** Given the wizard is used with keyboard only, when navigating steps and controls, then all controls are reachable, focus is visible, and step changes are announced.

### API Behaviour

| ID | Method & Path | Behaviour |
|---|---|---|
| API-1 | `POST /projects/drafts` | Creates a tenant-scoped creation draft; returns draft id; requires authenticated identity. Idempotent via client draft key. |
| API-2 | `PATCH /projects/drafts/{draftId}` | Updates draft fields (idea, metadata, portfolio, pipeline binding, tier selection/composition); performs optimistic concurrency via version token. |
| API-3 | `GET /projects/drafts/{draftId}` | Returns the draft with resolved pipeline/tier versions and pending validation results. |
| API-4 | `POST /projects/drafts/{draftId}/validate` | Runs full validation (tier composition, policy, credential resolution, pipeline compatibility) and returns a structured list of violations and overridables. |
| API-5 | `POST /projects/drafts/{draftId}/estimate` | Returns cost and latency bands for the draft's pipeline+tier combination, or an "unavailable" result with reason. |
| API-6 | `POST /projects/drafts/{draftId}/create` | Atomically creates the project; requires an idempotency key; returns the created project id, bound pipeline version, tier version, and audit reference. |
| API-7 | `GET /catalog/providers` | Lists providers with capability summaries; supports pagination and filtering. |
| API-8 | `GET /catalog/models` | Lists/searches models with filters (provider, capability, context window, modality, region, retirement). Paginated; cached. |
| API-9 | `POST /tiers` | Creates a new tier (or a new tier version when {tierId} is given); validates composition and persists immutably. |
| API-10 | `GET /tiers`, `GET /tiers/{tierId}` | Lists the tenant's tier library and returns a tier with its versions and coverage. |
| API-11 | `POST /tiers/{tierId}/clone` | Clones an accessible tier (including predefined) into a new editable tier owned by the caller. |
| API-12 | `POST /tiers/{tierId}/export` | Returns a portable tier document with provenance metadata. |
| API-13 | `POST /tiers/import` | Validates and imports a tier document; records provenance and returns a schema-path error list on failure. |
| API-14 | `POST /projects/bulk` | Accepts a list of project inputs sharing a pipeline+tier; returns a per-row outcome report; each row independently transactional and idempotent by row key. |
| API-15 | `GET /tier-policies` | Returns the tenant's default and allowed-tier policy used to constrain selection. |

All endpoints return structured problem details on error, including a machine-readable code, the offending field/schema path, and a retryability indicator. Mutating endpoints that can be safely retried accept an idempotency key.

### Priority

**must-have:** FR-26, FR-27, FR-28, FR-30, FR-31, FR-33, FR-34, FR-36, FR-37, FR-40, FR-41, FR-49, FR-50.
**should-have:** FR-29, FR-32, FR-35, FR-38, FR-39, FR-42, FR-44, FR-47, FR-48.
**nice-to-have:** FR-43, FR-45, FR-46.
