# Product Forge — Module IP-Value Assessment & Migration Inventory

**Status:** Canonical Architecture SSOT (Decision Record)  
**Scope:** Complete inventory and IP-value assessment of all Product Forge platform modules (`core/`, `api/`).  
**Backlog Reference:** `BI-PF-0386` (IP-value assessment of all modules)  
**Governing ADR & Baseline:** [`docs/ARCHITECTURE-DECISIONS.md`](ARCHITECTURE-DECISIONS.md) (ADR-0001), [`docs/PF-DELIVERY-BASELINE.md`](PF-DELIVERY-BASELINE.md) (BI-PF-0387), and [`docs/PF-TARGET-ARCHITECTURE-AND-IP-PLAN.md`](PF-TARGET-ARCHITECTURE-AND-IP-PLAN.md).  
**Machine-Readable Inventory:** [`config/module-ip-inventory.json`](../config/module-ip-inventory.json)

---

## 1. Executive Summary & Context

Product Forge is engineered as an enterprise-grade commercial platform delivered across multiple editions (Community, Developer, Commercial, Enterprise, Airgapped OEM) from a **single authoritative source repository**.

Under the **LOCKED delivery baseline** ([`docs/PF-DELIVERY-BASELINE.md`](PF-DELIVERY-BASELINE.md)) and ADR-0001:
1. **Never ship raw `.py` to customers:** Shipped customer packages consist exclusively of native compiled binaries (Go executables and Nuitka C-extensions).
2. **Go-First for new shipped logic:** Any new logic that ships in a customer edition and is sensitive is written in Go.
3. **Rewrite-by-Value Strangler Strategy:** Existing Python is not subjected to an uncontrolled, high-risk "big-bang" rewrite. Instead, platform modules are systematically classified by **intellectual property (IP) value, reverse-engineering sensitivity, and commercial criticality** to govern their progressive migration into Go/Rust.

This document establishes the definitive inventory of 340 platform modules across four governance tiers (`core/`, `api/`, and `adapters/`) and provides the technical rationale governing their migration priority.

---

## 2. Four-Tier Classification Model

| Tier | Category | Migration Target | Customer Distribution | Governance & Change Policy |
|---|---|---|---|---|
| **Tier 1** | **High IP / Sensitive** | **Go / Rust** (Priority 1) | Native compiled binary | New logic must land in Go; existing Python subjected to strict 20-line edit threshold; registered in `sensitive_roots`. |
| **Tier 2** | **Medium IP / Core Capabilities** | **Go** (Strangler Migration) | Native compiled binary (Nuitka stopgap until Go service cutover) | Edits permitted in Python up to 60 net added lines; rewrite scheduled by value and API domain boundaries. |
| **Tier 3** | **Low IP / Plumbing & Utilities** | **compiled-Python** | Nuitka C-extension binary (Zero readable `.py`) | Retained as compiled Python; lowest migration priority; low reverse-engineering sensitivity. |
| **Tier 4** | **Tooling & Build-Time** | **Python** | **Never shipped to customer** | Stays Python; excluded from customer edition packaging by the Runtime Dependency Compiler (RDC). |

---

## 3. Tier 1: High IP / Sensitive Modules (Rewrite Priority 1)

Tier 1 modules contain the core commercial, cryptographic, algorithmic, and architectural secrets of Product Forge. Exposure of these algorithms would directly compromise licensing enforcement, tenant security, or proprietary competitive advantages.

| Module | Domain | Sensitivity | Target | Architectural Rationale |
|---|---|---|---|---|
| `core/licensing.py` | Commercial | Critical | Go (`go/licensing`) | Cryptographic asymmetric license verification, entitlement-at-boundary enforcement, node lock. |
| `core/billing.py` | Commercial | Critical | Go (`go/edpsvc`) | Tenant credit metering, usage quotas, overage enforcement, and billing state. |
| `core/packaging.py` | Packaging | Critical | Go (`go/packaging`) | Commercial edition manifest compiler, component exclusion rules, binary signing orchestrator. |
| `core/release.py` | Release | High | Go | Release bundle integrity verification, cryptographic checksum generation, distribution control. |
| `core/credentials.py` | Security | Critical | Go | Provider API secrets management, hardware security module / vault integration, at-rest encryption. |
| `core/artifact_registry.py` | Packaging | High | Go | Proprietary build artifact indexing, tamper-evident signing verification, CAS storage. |
| `core/bom.py` | Governance | High | Go | Cryptographic SBOM/LBOM generation and license compliance register computation. |
| `core/sizing.py` | Architecture | High | Go | Proprietary resource, cost, memory, and latency estimation engine. |
| `core/deploy_providers.py` | Infrastructure | High | Go | Cloud deployment orchestration and proprietary infrastructure topology recipes. |
| `core/pipeline_executor.py` | Orchestration | Critical | Go (`go/pfcore`) | Core DAG pipeline execution engine, stage transitions, checkpoint recovery state machine. |
| `core/product_analyzer.py` | Intelligence | Critical | Go | Proprietary product specification intake, requirement decomposition, and feasibility analyzer. |
| `core/product_plan.py` | Planning | High | Go | Autonomous epic/feature dependency graph construction and phased milestone planner. |
| `core/service_catalog.py` | Architecture | High | Go | Service topology definitions, caller classes, and transport interface maps. |
| `core/global_orchestrator.py` | Orchestration | Critical | Go | Top-level autonomous multi-agent orchestration loop and consensus supervisor. |
| `core/intent_router.py` | Intelligence | High | Go | Natural language intent extraction, semantic dispatching, and agent capability routing. |
| `core/discovery_panel.py` | Reconnaissance | High | Go | Autonomous code discovery, architectural boundary mapping, and risk probing engine. |
| `core/discovery_engine.py` | Reconnaissance | High | Go | Deep static analysis and capability extraction algorithms. |
| `core/tech_stack.py` | Architecture | High | Go | Proprietary technology stack selection algorithms and framework compatibility matrices. |
| `core/model_strategy.py` | Model Gateway | High | Go | Dynamic model selection, token routing, latency/cost optimization, tier allocation. |
| `core/model_gate.py` | Model Gateway | High | Go | Model capability verification, hard token boundaries, and fail-closed security guards. |
| `core/pidl.py` | Language Engine | Critical | Go | Product Intent Definition Language compiler, AST validator, and cross-platform transpiler. |
| `core/agent_memory.py` | Intelligence | High | Go | Cross-agent semantic working memory and proprietary token-overlap associative index. |
| `core/conversation_models.py` | Intelligence | High | Go | Multi-agent execution context, session compilation, and distributed conversation state. |
| `core/capability_packs.py` | Architecture | High | Go | Dynamic capability composition and modular runtime bundle assembler. |
| `core/feasibility.py` | Intelligence | High | Go | Technical feasibility scoring, risk estimation, and architectural constraint validation. |
| `api/auth.py` | API Security | Critical | Go (`go/edpsvc`) | Inbound API authentication, token signature validation, tenant context binding. |
| `api/idempotency.py` | API Foundation | High | Go (`go/edpsvc`) | Distributed idempotency key management, replay attack protection, atomic lock reservation. |
| `api/envelope.py` | API Foundation | High | Go (`go/edpsvc`) | Canonical envelope serialization, tenant-scoped error masking, standard API contracts. |

---

## 4. Tier 2: Medium IP / Core Capabilities (Strangler Migration)

Tier 2 modules represent standard pipeline operations, domain logic, and governance components. They contain non-trivial business logic that is protected by Nuitka C-extension binary compilation today, and are prioritized for migration to Go based on API service boundaries.

* **Pipeline Execution & Coordination:** `core/agent_runner.py`, `core/stage_runner.py`, `core/worker.py`, `core/scheduler.py`, `core/job_manager.py`, `core/delegation.py`, `core/context_manager.py`.
* **Backlog & Engineering Flow:** `core/backlog.py`, `core/grooming.py`, `core/issues.py`, `core/change_spec.py`, `core/close_loop.py`, `core/engineering_flow.py`.
* **Quality & Compliance Verification:** `core/compliance_check.py`, `core/compliance_verifier.py`, `core/multi_model_review.py`, `core/agent_rules.py`, `core/change_policy.py`, `core/execution_trail.py`.
* **API Routers:** `api/routers/*.py` (thin HTTP routing adapters operating over canonical models).

**Governance:** Edits to existing Tier 2 Python modules are permitted within the 60-line net growth limit. When a domain crosses the threshold or requires horizontal scaling, it is factored into a Go service per ADR-0007 / ADR-0008.

---

## 5. Tier 3: Low IP / Plumbing & Utilities (Compiled Python Stopgap)

Tier 3 components provide auxiliary functions such as document formatting, report generation, asset templating, and label normalization. Their algorithmic IP value is low, and their security sensitivity is minimal.

* **Presentation & Documentation:** `core/pdf_generator.py`, `core/presentation_generator.py`, `core/marketing.py`, `core/workflow_docs.py`, `core/diagram_render.py`.
* **Onboarding & Formatting:** `core/customer_onboarding.py`, `core/human_readable_labels.py`, `core/naming.py`, `core/banner.py`, `core/artifact_formats.py`.
* **Package Initialization:** `core/__init__.py`, `api/__init__.py`, `api/routers/__init__.py`.

**Governance:** These modules are compiled into native shared objects (`.so` / `.pyd`) using Nuitka during edition packaging. They are maintained in Python with low priority for Go rewriting.

---

## 6. Tier 4: Tooling & Build-Time Only (Never Shipped)

Tier 4 comprises developer tooling, test frameworks, validation runners, and doc generators that execute strictly during Plane A development or CI/CD pipelines.

* **Test Frameworks:** `test-framework/**`, `tests/**`, `core/mock_*.py`.
* **Build & Dev Tooling:** `scripts/dev/**`, `scripts/pipeline.py`.
* **Templates & Schemas:** `templates/**`, `pipeline_templates/**`.

**Governance:** These modules are excluded from customer-facing edition builds by the Runtime Dependency Compiler (`BI-PF-0399`) and packaging gate (`BI-PF-0398`). They permanently stay in Python.

---

## 7. Configuration & Policy Integration

1. **Machine-Readable Store:** The authoritative inventory is stored at [`config/module-ip-inventory.json`](../config/module-ip-inventory.json) and registered in [`config/store-registry.json`](../config/store-registry.json) with single-writer `core/change_policy.py`.
2. **Sensitive Roots Enforcement:** All Tier 1 modules are registered in `sensitive_roots` in [`config/language-rule.json`](../config/language-rule.json) to enforce the strict 20-line edit growth threshold and mandate that all new sensitive logic lands in Go.
3. **Automated Verification:** The contract test suite in [`test-framework/tests/pipeline/test_module_ip_assessment.py`](../test-framework/tests/pipeline/test_module_ip_assessment.py) verifies that 100% of modules in `core/` and `api/` are accounted for with valid tiering and migration targets.

---

## 8. Definition of Done & Traceability

This assessment satisfies the requirements of **`BI-PF-0386`**:
- **AC-1:** Categorizes 100% of platform modules across Tier 1, Tier 2, Tier 3, and Tier 4.
- **AC-2:** Provides a machine-readable JSON inventory in `config/module-ip-inventory.json`.
- **AC-3:** Harmonizes `config/language-rule.json` sensitive roots with Tier 1 components.
- **AC-4:** Enforces complete coverage via automated contract tests.
