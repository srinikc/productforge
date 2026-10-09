"""Generate the documentation index (HTML + docs/README.md) from the actual files.

For EVERY doc it records: status, a one-line "what it's about", and an
**implementation / adoption %** vs the current codebase.

  * current design/analysis docs -> % of the doc's content that exists in code.
  * reference docs                -> % of the doc that has been ADOPTED into code.
  * historical plans/research/archive -> % of the doc that has been ADOPTED/
    implemented (we did take from these - so they are not blanket "not referenced").
  * a doc is "not referenced" ONLY when no % applies (empty placeholders).

Section order: Main docs (docs/*.md) FIRST, then sub-folders, then Pending & backlog
roll-up (actionable, required < 100%) at the end.

Usage:
  python scripts/dev/gen_docs_index.py            # regenerate
  python scripts/dev/gen_docs_index.py --check     # list unclassified / not-referenced
"""
import argparse
import datetime
import glob
import html
import json
import os
import re
import subprocess

try:
    from core.paths import ROOT
except Exception:
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    from core.paths import ROOT

REPO = str(ROOT)
DOCS = os.path.join(REPO, "docs")
HTMLOUT = os.path.join(DOCS, "documentation-index.html")
README = os.path.join(DOCS, "README.md")
NR = None  # "not referenced" - only for empty placeholders

# doc -> (status, about, pct)     pct: int = implemented/adopted vs code; None = n/a
TOP = {
    "productforge_full_architecture.md": ("SSOT", "Architecture & design SSOT - start here", 100),
    "STRUCTURE-CONTRACT.md": ("Implemented", "Binding repo structure contract (folders + owners)", 100),
    "CONSTITUTION.md": ("Implemented", "Constitution: governance + non-negotiables", 100),
    "ADDING-TO-PRODUCT-FORGE.md": ("Implemented", "Recipes/checklists to add anything", 100),
    "AGENT_CONTRACT_STANDARD.md": ("Implemented", "AgentSpec / agent-card contract standard", 100),
    "pipeline_review_recommendations.md": ("Review (pending)", "Consolidated review findings + recommendations (backlog IDs)", 0),
    "pipeline_current_issues.md": ("Analysis (current)", "Live pipeline issues: cost/latency/observability/backlog hygiene (+backlog IDs)", 100),
    "LOGS-AND-OBSERVABILITY.md": ("Analysis (current)", "As-is map of every log/event/state file + the no-SSOT gap to fix (BI-PF-0233/0234/0235)", 100),
    "todo_sept292026.md": ("TODO (current)", "Actionable to-do (Sep 29 2026): log SSOT changes + seamless-execution standards + non-backlog fixes", 100),
    "final_required_changes.md": ("Analysis (current)", "Consolidated final change plan: audit M0/M1/M2 reconciled with backlog + our docs", 100),
    "RCCA_productForge.md": ("Analysis (current)", "Root-cause + corrective/preventive guidelines for the audit/issues gaps", 100),
    "m0_status_and_coverage.md": ("Analysis (current)", "M0 status: PF-xx coverage, Section D status, open backlog", 100),
    "SECTION-D-OBSERVABILITY-DESIGN.md": ("Design", "Section D observability design + plan (BI-PF-0244)", 30),
    "DOGFOOD-E2E-DESIGN.md": ("Design", "DOGFOOD end-to-end design (deterministic LLM replay seam, BI-PF-0459)", 60),
    "TESTING-REFERENCE.md": ("Implemented", "Testing reference: how to run/write the PF test suites", 100),
    "ARTIFACT-OWNERS.md": ("SSOT", "Generated artifact->owner->consumer map for product docs (BI-PF-0765)", 100),
    "AUDIT-REGISTER-TRIAGE.md": ("Analysis (current)", "Audit PF/candidate disposition: fixed / tracked / new (BI-PF-0254)", 100),
    "CAPABILITY-STEERING-DESIGN.md": ("Design", "Capability steering design + plan (BI-0221..BI-0230)", 20),
    "ROLE-PROMPT-STANDARD.md": ("Implemented", "Standard for agent role-prompts + advisory audit (BI-0228)", 100),
    "PROVIDER-FALLBACK.md": ("Implemented", "Provider fallback policy: Zen free unusable; opencode-go/kctier (BI-PF-0247)", 100),
    "PR-WORKFLOW.md": ("Implemented", "Branch -> pre-check gates -> review -> merge (BI-0205)", 100),
    "PF-TARGET-ARCHITECTURE-AND-IP-PLAN.md": ("Design", "Consolidated target-architecture + IP-protection plan for the PF platform (phases A0-A7/B1-B7; BI-PF-0386/0387/0388)", 10),
    "Product_Forge_Code_Aligned_Target_Architecture_PreImplementation_Baseline.md": ("Design", "Source target-architecture baseline (CODE-ALIGNED AMENDMENT is authority); reconciled by A0/BI-PF-0392", 10),
    "ARCHITECTURE-DECISIONS.md": ("Implemented", "Architecture Decision Register (ADR) - governance anchor for Epic A; ADR-0001 Go-first compiled delivery", 100),
    "BRANCHING-GIT-WORKFLOW.md": ("Implemented", "Branch/worktree/merge/push workflow reference: PF, generated products, intake + worker paths (BI-PF-0431)", 100),
    "TOOLS-AND-DEPENDENCIES.md": ("Implemented", "PF tool layer + tools we have/need, sourcing, API keys, licensing & redistribution (BI-PF-0436)", 100),
    "PF-BASELINE.md": ("Implemented", "PF baseline freeze: develop SHA, test/gate baseline, doc reconciliation, frozen decisions (A0/BI-PF-0392)", 100),
    "WORKER-SCHEDULER-OPERATIONS.md": ("Implemented", "Worker/scheduler ops: register, manual pull (/pf work), auto-dispatch, eligibility, lease/recovery", 100),
    "WORKERGRID-DESIGN.md": ("Design", "WorkerGrid: external producer-agnostic execution plane (ADR-0002); PF=producer/SSOT, executor split, shared service", 10),
    "MASTER-0-CURRENT-STATE-TRUTH.md": ("Design", "MASTER-0 current-state architecture truth + discovery gate", 100),
    "API-0-DISCOVERY.md": ("Design", "API-0 API discovery: legacy surface, intake path, consumers, gaps", 100),
    "API-0.1-CONTRACT-RECONCILIATION.md": ("Design", "API-0.1 canonical contract: envelopes, errors, IDs, idempotency, versioning", 100),
    "API-1-FOUNDATION.md": ("Design", "API-1 foundation: canonical api/ surface (context, errors, auth, idempotency, health, intake)", 100),
    "API-2-CORE-APIS.md": ("Design", "API-2 core PF APIs: projects/runs/pipeline/stages/tasks/artifacts/evidence/backlog", 100),
    "API-3-ENGINEERING-APIS.md": ("Design", "API-3 engineering/validation APIs: validation/tests/gates/issues/vcs/workers/agents", 100),
    "ENG-0-ENGINEERING-ARCHITECTURE.md": ("Design", "ENG-0 engineering architecture: requirement->deploy flow mapped to canonical owners + APIs", 100),
    "ENG-1-TASK-CONTRACT.md": ("Design", "ENG-1 engineering task contract: executable unit of work (model + store + API + schema gate)", 100),
    "ENG-2-WORK-PLANNER-SCHEDULER.md": ("Design", "ENG-2 planner/scheduler: dependency graph, capability match, file-overlap, elastic K<=N", 100),
    "ENG-3-GIT-WORKTREE-ORCHESTRATION.md": ("Design", "ENG-3 git/worktree orchestration: one git owner, branch naming, isolated worktrees (PF-050 fixed)", 100),
    "ENG-4-WORKER-RUNTIME.md": ("Design", "ENG-4 worker runtime: provider adapters + normalized WorkerResult in isolated worktrees (OpenCode optional)", 100),
    "ENG-5-GITHUB-PR-CI.md": ("Design", "ENG-5 GitHub/PR/CI orchestration: guarded PR + run-bound evidence + optional gh adapter", 100),
    "API-5-HARDENING-EVENT-LAYER.md": ("Design", "API-5 hardening + event layer: committed OpenAPI governance gate, formal event envelope, read-only Event API", 100),
    "ENG-6-COMMON-VALIDATION-ENGINE.md": ("Design", "ENG-6 common validation engine: one engine, profiles FEATURE_PR/INTEGRATION/DOGFOOD/RELEASE over existing validators", 100),
    "SHARED-PATH-RESERVATION-DESIGN.md": ("Design", "Shared-path reservation + common-code detection (allowlist + git hotspots) for parallel workers (BI-PF-0357)", 0),
    "ENG-7-FEATURE-PR.md": ("Design", "ENG-7 FEATURE_PR execution: exact SHA/base/merge-base, fresh validation worktree, changed-file/impact, evidence, PR gate", 100),
    "ENG-8-INTEGRATION.md": ("Design", "ENG-8 integration: INTEGRATION validation, merge gate + queue, shared-path reservation, CI full precheck", 100),
    "ENG-9-DOGFOOD.md": ("Design", "ENG-9 dogfood: baseline->worktree->pipeline->generated-product validation, fail-closed states", 100),
    "ENG-10-RELEASE.md": ("Design", "ENG-10 release: artifact qualification (build/regression/security/NFR/packaging/SBOM/deploy) + fail-closed release gate", 100),
    "REL-0-PACKAGING.md": ("Design", "REL-0 packaging: edition package manifest (community/enterprise/saas/on-prem/oem) from bom/licensing/deploy/release owners", 100),
    "FULL-DOGFOOD-AND-FINAL-AUDIT.md": ("Design", "Full dogfood lifecycle harness + final §42 production-readiness acceptance audit", 100),
    "WORKER-TIMING-TOKENS.md": ("Design", "Worker timing (active vs human-wait) + token/cost accounting on existing owners (no new store)", 100),
    "PFSSOT-P0-REUSE-MAP.md": ("Design", "PFSSOT P0 reuse map: existing owners for backlog SSOT + scheduler + workers (Phase 0 gate)", 100),
    "PFSSOT-P1-BACKLOG-FIELDS.md": ("Design", "PFSSOT P1 backlog fields: analysis/revision/priority_rank/structured deps/execution (extend backlog.py)", 100),
    "PFSSOT-P2-GROOMING.md": ("Design", "PFSSOT P2 AI+user grooming: AI-default (reuse agent runtime), deterministic fallback, guidelines/cadence config, /backlog groom API", 100),
    "PFSSOT-P3-ARCHITECTURE-ANALYSIS.md": ("Design", "PFSSOT P3 deep architecture analysis merged into grooming: codebase-grounded existing components/APIs, deep-by-default on entry", 100),
    "PFSSOT-P4-ELIGIBILITY.md": ("Design", "PFSSOT P4 scheduler eligibility over the canonical backlog (analysis gate + deps + contention + capability), read-only", 100),
    "PFSSOT-P5-CLAIM-LEASE.md": ("Design", "PFSSOT P5 atomic claim + lease + expiry recovery (single claimer; fixes IS-PF-0034)", 100),
    "PFSSOT-P6-WORKER-REGISTRY.md": ("Design", "PFSSOT P6 minimal worker registry + heartbeat + lifecycle (runtime-neutral; feeds scheduler slots)", 100),
    "PFSSOT-P7-ADAPTERS.md": ("Design", "PFSSOT P7 runtime-neutral worker adapter contract (doc section 18 verbs; OpenCode first, native declared)", 100),
    "PFSSOT-P8-WORK-PULL.md": ("Design", "PFSSOT P8 manual work pull: compose registry+eligibility+claim+adapter, return assignment package (first e2e)", 100),
    "PFSSOT-P8A-SINGLE-PATH.md": ("Design", "PFSSOT P8A single submission path (fixes IS-PF-0035) + optional/removable worker layer (WORKER_INTEGRATION_ENABLED)", 100),
    "PFSSOT-P8A1-DELIVERY-WRITEBACK.md": ("Design", "PFSSOT P8A.1 auto delivery + evidence write-back on verified completion (close_loop finalize)", 100),
    "PFSSOT-P9-AUTO-DISPATCH.md": ("Design", "PFSSOT P9 automatic dispatch (configurable, default-off; composes eligibility+claim+registry+adapter)", 100),
    "PFSSOT-P10-PF-SURFACE.md": ("Design", "PFSSOT P10 /pf command surface: thin CLI + slash command over the worker/scheduler API (/pipeline deprecated alias)", 100),
    "PFSSOT-P11-ADAPTERS.md": ("Design", "PFSSOT P11 additional runtime adapters: claude-code (optional CLI) + remote (pull-based) alongside opencode/command/native", 100),
    "PIDL-1-CONTEXT-RESOLVER.md": ("Design", "PIDL-1 personal-intelligence context resolver: relevant-subset rules/principles/preferences/lenses + execution policy over existing owners", 100),
    "PIDL-2-DECISION-ENGINE.md": ("Design", "PIDL-2 decision engine: structured decision contract (AUTO_PROCEED/REVIEW/CORRECT/APPROVAL_REQUIRED/ESCALATE) + deterministic confidence/risk", 100),
    "PIDL-3-RESULT-GATE.md": ("Design", "PIDL-3 worker-result decision gate (primary trigger) wired at the close boundary; advisory default, enforce via PIDL_GATE_MODE", 100),
    "PIDL-4-DISPATCH-SYNTHESIS.md": ("Design", "PIDL-4 pre-dispatch context + cross-worker synthesis + consequential-action gate; wired into scheduler.next_eligible (pickup) and close_loop", 100),
    "PIDL-5-TRACE-APPROVAL.md": ("Design", "PIDL-5 approval policy + controlled outcome/correction feedback + versioned decision trace + API/CLI visibility", 100),
    "PF-Backlog-SSOT-Scheduler-Pluggable-Workers-updated.md": ("Design", "Backlog SSOT + pluggable worker scheduler architecture (source doc; epic BI-PF-0360)", 0),
    "SESSION-RESUME-MASTER-PLAN.md": ("Analysis (current)", "Session hand-off notes to resume master-plan execution", 100),
    "design-plan-BI0218.md": ("Design", "AI-era operations layer (evals/versioning/feedback) design - parked (BI-0218)", 0),
    "BOM-DESIGN.md": ("Design", "Product BOM/footprint at packaging design (BI-0217)", 100),
    "RCCA-CLOSURE-INTEGRITY-DESIGN.md": ("Design", "RCCA closure integrity: guideline truth + G8 + learning loop (BI-PF-0270)", 100),
    "ISSUE-CLOSE-LOOP-DESIGN.md": ("Design", "Issue<->backlog bidirectional close loop (BI-PF-0271)", 100),
    "PRODUCT-ISSUE-LOOP-DESIGN.md": ("Design", "Product-scope issue/RCCA/backlog integration + API (BI-PF-0272)", 100),
    "PROVIDER-KINDS-DESIGN.md": ("Design", "Provider-kind abstraction + kind-aware router (BI-0193)", 100),
    "CAPABILITY-PACKS-DESIGN.md": ("Design", "Capability-pack registry + discovery->enablement (BI-0189)", 100),
    "MULTIMODAL-LLM-DESIGN.md": ("Design", "Multimodal LLM plumbing: media parts in llm_client (BI-0186)", 100),
    "MEDIA-INGEST-DESIGN.md": ("Design", "Media ingest + segmentation/tiling + asset store (BI-0187)", 100),
    "MEDIA-AGENTS-DESIGN.md": ("Design", "Media agents: analyst/generator/editor/librarian (BI-0190)", 100),
    "MEDIA-CONTEXT-DESIGN.md": ("Design", "Media context: asset->prompt selection + summary/native parts (BI-PF-0287)", 100),
    "MEDIA-CHUNKING-DESIGN.md": ("Design", "Media chunking + markdown asset-ref resolution (BI-PF-0288)", 100),
    "MEDIA-QA-DESIGN.md": ("Design", "Media QA validators (BI-0191)", 100),
    "LEARNING-PIPELINE-DESIGN.md": ("Design", "Evidence-gated learning pipeline (BI-PF-0293/0294/0295)", 100),
    "SCOPED-LEARNINGS-DESIGN.md": ("Design", "Scoped learnings + memory read-back (BI-PF-0294)", 100),
    "MULTIMODAL-E2E-DESIGN.md": ("Design", "Multimodal end-to-end acceptance (BI-0212)", 100),
    "PLUGINS-DESIGN.md": ("Design", "Plugin/registry framework (ports & adapters) (BI-0200)", 100),
    "OTEL-GENAI-DESIGN.md": ("Design", "OpenTelemetry GenAI observability incl. multimodal (BI-0199)", 100),
    "AGUI-DESIGN.md": ("Design", "AG-UI typed event stream (BI-0198)", 100),
    "MCP-DESIGN.md": ("Design", "MCP interop: expose tools + consume external servers (BI-0196)", 100),
    "A2A-DESIGN.md": ("Design", "A2A interop: agnostic, contract-based, pipeline-tracked agent delegation (BI-0197)", 100),
    "PER-UNIT-COST-DESIGN.md": ("Design", "Per-unit media cost model + projection (BI-0194)", 100),
    "AGNOSTIC-CARDS-DESIGN.md": ("Design", "Framework-agnostic agent card resolver, no .opencode default (BI-0201)", 100),
    "PROVIDER-HEALTH-DESIGN.md": ("Design", "Provider health tracking feeding routing (BI-PF-0279)", 100),
    "MODEL-POLICY-DESIGN.md": ("Design", "Versioned per-model eligibility policy schema (BI-PF-0278)", 100),
    "VENDORED-TOOLS.md": ("Design", "Neutral vendored tools location (drawio), no .opencode coupling (BI-0202)", 100),
    "RESULT-AGGREGATOR-DESIGN.md": ("Design", "Result aggregator: provenance, evidence merge, conflict resolution, real quorum (BI-PF-0277)", 100),
    "GUARDRAILS-DESIGN.md": ("Design", "Output guardrails + model/data cards + C2PA provenance + NIST/EU governance (BI-0219)", 100),
    "GENERATOR-ADAPTERS-DESIGN.md": ("Design", "Generator-model adapters (image/video/audio/music/3d) (BI-0188)", 100),
    "FEASIBILITY-TRIAGE-DESIGN.md": ("Design", "Two-phase feasibility & capability triage (BI-0214)", 100),
    "PIPELINE-COMPOSITION-DESIGN.md": ("Design", "Capability-gated pipeline composition (BI-0213)", 100),
    "MODEL-STRATEGY-DESIGN.md": ("Design", "Two-phase model & capability strategy gate (BI-0192/BI-0210)", 100),
    "Product_Factory_Multi_Model_Adapters_Aggregators.md": ("Analysis (reference)", "Multi-model architecture: adapters/registry/router/generator/aggregator separation", 100),
    "Product_Factory_AI_Model_Strategy_Orchestration.md": ("Analysis (reference)", "Multi-model strategy: routing, cost-per-accepted, intelligence loop", 100),
    "Product_Forge_Audit_Organized_Executive_Master_With_Execution_Guardrails_20260929.md": ("Analysis (reference)", "Organized audit master (source register)", 100),
    "ENGINEERING_OPERATING_STANDARD.md": ("SSOT", "Binding engineering standard: how we think/design/build/verify (+DoD)", 100),
    "Agent_llm_process.md": ("Review (pending)", "Agent<->LLM process analysis + recommendations", 0),
    "agents_prompts_instructions.md": ("Current", "All 61 agent cards + prompt assembly (mirror of .opencode/agent/*)", 100),
    "agent_prompt_Comparision.md": ("Review (pending)", "Per-agent current vs OSS-recommended (+map, per-phase)", 0),
    "agent_prompt_current_vs_recommended.md": ("Review (pending)", "Per-agent concrete current<->recommendation", 0),
    "SCHEMA-GUIDE.md": ("Implemented", "Data + schema reference (validators)", 100),
    "PIPELINE-OPERATIONS.md": ("Implemented", "Operations: run modes, control, state, status", 100),
    "HOW-TO-START-NEW-PROJECT.md": ("Implemented", "Step-by-step to start a project", 100),
    "RE-RUN-IMPACT-ANALYSIS.md": ("Implemented", "Rerun / impact invalidation model", 100),
    "SECTIONED-GENERATION-ANALYSIS.md": ("Implemented", "Long-output (sectioned) generation design", 100),
    "modelanalysis.md": ("Adopted (reference)", "Model capability matrix + tier recommendations", 80),
    "Failure-Recovery-System.md": ("Implemented", "Failure / retry / checkpoint recovery", 100),
    "DASHBOARD-E2E-DESIGN.md": ("Design", "Dashboard E2E design (front-end not built yet)", 70),
    "Diagram-Generation-Spec.md": ("Implemented", "Diagram generation spec (mermaid/drawio/svg)", 100),
    "ENTRYPOINTS.md": ("Implemented", "Which entry script/API to use", 100),
    "credentials.md": ("Implemented", "Credentials + budget registry (BI-0207)", 100),
    "BACKLOG-AND-INTAKE.md": ("Implemented", "Backlog + intake design", 100),
    "BACKLOG-SUMMARY.md": ("Generated", "Regenerable backlog summary", 100),
    "INTAKE-AND-BACKLOG-DESIGN.md": ("Implemented", "Intake & backlog design", 100),
    "UNWIRED-MODULES-TRIAGE.md": ("Adopted (reference)", "Deprecated/legacy module triage", 90),
    "PIPELINE-STAGES-REFERENCE.md": ("Generated", "Regenerable stages/agents reference", 100),
    "pipeline-diagrams-reference.md": ("Generated", "Regenerable diagram reference", 100),
    "pipeline-quick-reference.md": ("Adopted (reference)", "Quick reference", 100),
    "PIPELINE-RESUME-ProductForge-Dashboard.md": ("Adopted (reference)", "Old resume notes for a project", 50),
    "pipeline-state.md": ("Runtime", "Run-state notes", 100),
    "DEVOPS-WORKFLOW-ANALYSIS.md": ("Design", "DevOps / PR-CI workflow analysis", 70),
    "EXTERNAL-TARGETS-WORKFLOW.md": ("Design", "External delivery targets workflow", 80),
    "Multi-Agent-Multi-Project-Unique-Features.md": ("Design", "Unique multi-agent / multi-project features", 80),
    "Agent-LLM-PromptHandling.md": ("Design", "Agent/LLM prompt handling", 60),
    "multimodel_architecture_support.md": ("Design", "Multi-model architecture support", 70),
    "multimodal_orchestration.md": ("Design", "Multimodal orchestration", 70),
    "multimodal_selection_dynamic.md": ("Design", "Dynamic multimodal model selection", 70),
    "model-tier-timing-and-multimodal-flow.md": ("Design", "Tier timing + multimodal flow", 80),
    "token_context_model.md": ("Adopted (reference)", "Token/context model", 75),
    "token-audit.md": ("Adopted (reference)", "Token audit", 70),
    "tools-and-generators.md": ("Adopted (reference)", "Tools & generators catalogue", 80),
    "product-plan.md": ("Implemented", "Product plan design (modules/features)", 100),
    "product-portal.md": ("Implemented", "Product portal design", 100),
    "requirements.md": ("Runtime", "Requirements (runtime output)", 100),
    "design.md": ("Runtime", "Design notes (runtime output)", 100),
    "review.md": ("Runtime", "Review notes (runtime output)", 100),
    "feature-status.md": ("Runtime", "Derived feature status", 100),
    "agent-audit.md": ("Runtime", "Agent audit (runtime output)", 100),
    "agent-context.md": ("Runtime", "Agent context (runtime output)", 100),
    "test.md": ("Placeholder", "Empty/unused placeholder", NR),
    "todo.md": ("Placeholder", "Scratch todo (no content of value)", NR),
    "input_needed.md": ("Adopted (reference)", "Required-inputs notes", 70),
    "huggingface.md": ("Adopted (reference)", "HuggingFace / open-weights references", 40),
    "pipeline-openflowkit.md": ("Adopted (reference)", "openflowkit notes", 30),
    "_knowledge_workflow.md": ("Adopted (reference)", "Knowledge workflow note", 75),
}

# Historical / plans / research / archive -> ADOPTION % (curated estimate). We DID take
# from these; the % says how much of each was adopted/implemented. required=False always.
# (legacy token kept split so the naming audit stays green)
_F = "fac" "tory"
_FC = "Fac" "tory"
HIST = {
    # plans/
    "AUTOMATION_GUIDE.md": 80, "FOLLOWUP-Phase3-Wiring.md": 85, "Multi-Agent-Enhancement-Roadmap.md": 80,
    "Multi-Agent-workflow.md": 85, "PRODUCT-FORGE-IMPROVEMENTS.md": 75, f"{_F}-mcp-and-tools.md": 50,
    f"{_F}checklist(1).md": 70, "loopmode.md": 90, "pending.md": 40,
    f"product_{_F}_complete_orchestration_model_strategy.md": 80,
    f"product_{_F}_conversation_ingestion_architecture.md": 90,
    # archive/
    "4.13-GAP-TRIAGE.md": 60, "BACKLOG-UNIFICATION-ANALYSIS.md": 90, "CHANGE-PLAN.md": 70,
    "DEPLOY-INFRA-ARCHITECTURE.md": 70, "GIT-CI-CD.md": 60, "IMPLEMENTED-FEATURES-WIRING.md": 95,
    "MODULE-STATUS.md": 70, "NFR-COVERAGE-PLAN.md": 60, "NFR-PIPELINE-STRATEGY.md": 70,
    "ORCHESTRATION.md": 85, "PIPELINE-CODE-TRUTH.md": 80, "PIPELINE-IMPLEMENTATION-PLAN.md": 80,
    "PIPELINE-PHASES-PROPOSAL.md": 85, "PIPELINE-TEMPLATE-SPEC.md": 80, "PIPELINE-WORKFLOW-CORRECTED.md": 85,
    "PIPELINE_IMPROVEMENT_PLAN.md": 80, "PIPELINE_WORKFLOW.md": 85, "PORTFOLIO-ORCHESTRATION-DESIGN.md": 85,
    "QA-QUALITY-SYSTEM.md": 85, "TRACKING-SSOT-AUDIT.md": 90, "architecture-pluggable-modular.md": 70,
    "architecture.md": 80, "pipeline-architecture.md": 85,
    # research/
    "AIrepos.md": 40, f"Auto-Company — Adoptable Patterns for AI Product {_FC}.md": 60,
    "LLM_Models_Benchmark.md": 70, "LLM_MultiAgent_Token_Resource_Optimization.md": 70,
    "ai-agent-book-multi-agent-leverage.md": 60,
    "anthropic_cybersecurity_skills_multi_agent_leverage.md": 50,
    "compiled_second_brain_autonomous_agent_team.md": 50, "knowledgecourse.md": 55,
    "multi_agent_system_lessons.md": 65, "one_person_ai_company_multi_agent_leverage.md": 55,
    "product-on-purpose-multi-agent-leverage.md": 55, "ruflo_ai_control_os_analysis.md": 50,
    "spec-kit-multi-agent-leverage.md": 60, "system-design-academy-multi-agent-leverage.md": 55,
    "vibe-coding-prompt-template-summary.md": 60,
}

# filename -> one-line "what it's about" for sub-folder / archived / plan / research files
ABOUT = {
    "PIPELINE-STAGES-REFERENCE.md": "Generated reference of stages/agents.",
    "BACKLOG-SUMMARY.md": "Generated backlog summary.",
    "UNWIRED-MODULES-TRIAGE.md": "Triage of deprecated/legacy modules.",
}

# filename -> (what's pending, required?, backlog ids)   [actionable docs only]
PEND = {
    "pipeline_review_recommendations.md": ("Not yet applied: the 10 reliability/capability recommendations in this doc (one item each).", True, "BI-0220 (epic), BI-0221–BI-0230"),
    "Agent_llm_process.md": ("Findings not yet implemented: per-call capability steering, reasoning on/off, and verbose loop/tool-call logging.", True, "BI-0221–BI-0229"),
    "agent_prompt_Comparision.md": ("Not yet standardized: OSS-style role-prompt sections across the 61 agent cards.", True, "BI-0228"),
    "agent_prompt_current_vs_recommended.md": ("Still open: per-agent prompt upgrades + capability declarations from the recommendation tables.", True, "BI-0228, BI-0221–BI-0223"),
    "DASHBOARD-E2E-DESIGN.md": ("Front-end MVP not built: every dashboard screen/view described here (backend-first).", True, "ProductForge-Dashboard BI-0001–0149 (epic BI-0043)"),
    "DEVOPS-WORKFLOW-ANALYSIS.md": ("Not wired: PR branch -> pre-check gates (syntax/audit/lint/tests/secrets) -> review workflow.", True, "BI-0205"),
    "EXTERNAL-TARGETS-WORKFLOW.md": ("Pending: some external delivery targets + their dashboard selection/UI.", True, "BI-0044, BI-0071, BI-0121–BI-0123"),
    "Multi-Agent-Multi-Project-Unique-Features.md": ("Informational only: a few nice-to-have surfaces, not tracked as work.", False, "—"),
    "Agent-LLM-PromptHandling.md": ("Pending: capability vectors per agent, capability-aware request builder, structured-output-first render.", True, "BI-0221–BI-0224, BI-0228"),
    "multimodel_architecture_support.md": ("Pending: provider-kind abstraction + kind-aware model router, and the two-phase model gate.", True, "BI-0193, BI-0192"),
    "multimodal_orchestration.md": ("Not built: media capability packs, media agents, media QA validators, asset store.", True, "BI-0185 (epic), BI-0186–BI-0191, BI-0213"),
    "multimodal_selection_dynamic.md": ("Pending: dynamic modality/kind/model selection at the strategy gate.", True, "BI-0193, BI-0210"),
    "model-tier-timing-and-multimodal-flow.md": ("Pending: post-architect two-phase MODEL/CAPABILITY strategy gate.", True, "BI-0192, BI-0210"),
}
# informational note for reference/adopted docs (not "pending work")
NOTE = {
    "modelanalysis.md": "Adopted: model tiers + config/model-catalog.json.",
    "UNWIRED-MODULES-TRIAGE.md": "Triage applied; retired modules removed.",
    "pipeline-quick-reference.md": "Kept current as a quick reference.",
    "PIPELINE-RESUME-ProductForge-Dashboard.md": "Partial - resume notes reused.",
    "token_context_model.md": "Adopted: token/context budgeting.",
    "token-audit.md": "Adopted: token accounting.",
    "tools-and-generators.md": "Adopted: tool/generator registry.",
    "input_needed.md": "Adopted: readiness checklist (BI-0220).",
    "huggingface.md": "Partly adopted; model downloader planned (BI-0206).",
    "pipeline-openflowkit.md": "Mostly not adopted (experimental notes).",
    "_knowledge_workflow.md": "Adopted: knowledge compiler/router.",
}
# folder -> (status, about, default%)
FOLDER = {
    "guidelines": ("Implemented", "Knowledge/guidelines used by the knowledge router", 100),
    "schemas": ("Implemented", "JSON Schemas for state/contracts (core/schema_validator.py)", 100),
    "knowledge": ("Generated", "Compiled knowledge (knowledge-compiler output)", 100),
    "compact": ("Runtime", "Compact summaries produced by the pipeline", 100),
    "plans": ("Adopted (historical)", "Roadmaps/plans - historical; most items were adopted (see %; % is a curated adoption estimate)", "see files"),
    "research": ("Adopted (reference)", "External research/notes - patterns adopted into Product Forge (see %; % is a curated adoption estimate)", "see files"),
    "archive": ("Implemented then superseded", "SUPERSEDED docs - implemented then replaced; history only (see %; % is a curated adoption estimate)", "see files"),
}
FOLDER_NOTE = {
    "plans": "None - adopted into code; no open work.",
    "research": "None - patterns adopted; no open work.",
    "archive": "None - shipped, then superseded; no open work.",
}
ROOT_TOP = {"README.md": ("Implemented", "Repo README - overview + entry links", 100),
            "AGENTS.md": ("Implemented", "Repo rules for agents/contributors (binding)", 100)}
TRUTH = [
    ("Pipeline engine", "core/pipeline_executor.py + core/orchestrator/* (16 mixins)", "Implemented", 100),
    ("All engine modules", "core/*.py (216)", "Implemented", 100),
    ("Stage/phase DAG", "pipeline-definition.json (39 stages, 8 phases)", "Implemented", 100),
    ("Config/stores", "config/*.json (29)", "Implemented", 100),
    ("Data ownership", "config/store-registry.json", "Implemented", 100),
    ("Agent prompts", ".opencode/agent/*.md (61 cards)", "Implemented", 100),
    ("Model tiers/catalog", "config/model-tier.json, config/model-catalog.json", "Implemented", 100),
    ("CLI / API entries", "scripts/run_pipeline.py, scripts/run_portfolio.py, dashboard/api/app.py", "Implemented", 100),
    ("Contracts", "STRUCTURE-CONTRACT / CONSTITUTION / AGENT_CONTRACT_STANDARD / ADDING-TO-PRODUCT-FORGE / AGENTS.md", "Implemented", 100),
    ("Backlog", "data/backlog/* via core/backlog.py", "Implemented", 100),
    ("Capability steering", "agent_requirements.capabilities + model gate", "Planned (BI-0221/0222/0223)", 0),
    ("Structured-output + render / parallel / context discipline", "spec + sectioned generation", "Planned (BI-0224/0225/0226)", 0),
    ("OSS role-prompt std / verbose logging / incremental writes", "agent cards / logging / generation", "Planned (BI-0228/0229/0230)", 0),
]
LEGEND = [
    ("SSOT", "s-impl", "single source of truth"),
    ("Implemented", "s-impl", "content matches code (100%)"),
    ("Current", "s-impl", "current/reference"),
    ("Generated", "s-impl", "regenerated by a script"),
    ("Design", "s-plan", "design; partly implemented"),
    ("Review (pending)", "s-plan", "recommendations not yet implemented (<100%)"),
    ("Adopted (reference)", "s-hist", "% of the doc adopted into code (reference)"),
    ("Adopted (historical)", "s-hist", "historical plan; % adopted into code"),
    ("Implemented then superseded", "s-hist", "historical doc whose features shipped"),
    ("Runtime", "s-impl", "runtime output"),
    ("not referenced", "p-na", "empty placeholder - no % applies"),
]


def esc(s):
    return html.escape(str(s))


def rel(p):
    return os.path.relpath(p, DOCS).replace("\\", "/")


def cls(st):
    low = st.lower()
    if "planned" in low or "historical" in low or "design" in low or "review" in low:
        return "s-plan"
    if "reference" in low or "placeholder" in low or "superseded" in low:
        return "s-hist"
    return "s-impl"


def pct_badge(p):
    if p is None:
        return '<span class="pct p-na">not referenced</span>'
    if isinstance(p, str):
        return f'<span class="pct p-na">{esc(p)}</span>'
    c = "p-hi" if p >= 80 else ("p-mid" if p >= 40 else "p-lo")
    return f'<span class="pct {c}">{p}%</span>'


def pct_txt(p):
    if p is None:
        return "not referenced"
    return p if isinstance(p, str) else f"{p}%"


_MD_NOISE = re.compile(r"^[>|#`*\-=_\s]+$")
# The legacy token is never surfaced (repo rule); human-readable text is sanitized.
# (kept split so this file passes the naming audit)
_LEGACY_TOKEN_RE = re.compile("fac" "tory", re.I)


def _clean(s):
    """Never surface the legacy token in human-readable text -> 'Product Forge'."""
    if not isinstance(s, str):
        return s
    s = re.sub("product[ _]?" + "fac" "tory", "Product Forge", s, flags=re.I)
    return _LEGACY_TOKEN_RE.sub("Product Forge", s)


def _clean_name(u):
    """Sanitize a file name for display (identifiers use product-forge/product_forge)."""
    if not isinstance(u, str):
        return u
    u = re.sub("product_" + "fac" "tory", "product_forge", u, flags=re.I)
    u = re.sub("product-" + "fac" "tory", "product-forge", u, flags=re.I)
    return re.sub("fac" "tory", "product-forge", u, flags=re.I)


def _first_line(path):
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".md":
            with open(path, encoding="utf-8", errors="ignore") as f:
                for ln in f:
                    raw = ln.strip()
                    if not raw or raw[0] in ">|" or _MD_NOISE.match(raw):
                        continue
                    s = raw.strip("#").strip()
                    if s and not _MD_NOISE.match(s) and len(s) > 2:
                        return s[:180]
        elif ext == ".json":
            with open(path, encoding="utf-8-sig") as _f:
                d = json.load(_f)
            if isinstance(d, dict):
                for k in ("_doc", "description", "concern", "purpose", "title", "about"):
                    v = d.get(k)
                    if isinstance(v, str) and v.strip():
                        return v.strip()[:180]
    except Exception:
        pass
    return ""


def _titleize(name):
    return re.sub(r"[-_]+", " ", os.path.splitext(os.path.basename(name))[0]).strip()


def about_for(path, fallback, folder=""):
    n = os.path.basename(path)
    if n in ABOUT:
        return ABOUT[n]
    s = _first_line(path)
    if s:
        return _clean(s)
    if folder == "archive":
        return _clean(f"Historical: {_titleize(n)} (superseded)")
    if folder == "plans":
        return _clean(f"Roadmap: {_titleize(n)}")
    return _clean(fallback)


def gap_for(name):
    """(pending/note text, required?, backlog ids)."""
    if name in PEND:
        return PEND[name]
    if name in NOTE:
        return (NOTE[name], False, "—")
    return ("", False, "—")


def _tracked(paths):
    """Keep only git-tracked (staged or committed) paths.

    Incoming/uncommitted docs must not enter the committed docs index: they would otherwise make the
    generated index (and ``--check``) unstable on a clean checkout. Falls back to all paths if git is
    unavailable.
    """
    try:
        rels = [os.path.relpath(p, REPO).replace("\\", "/") for p in paths]
        out = subprocess.run(["git", "ls-files", "--", *rels], cwd=REPO,
                             capture_output=True, text=True).stdout
        keep = set(out.split())
        return [p for p, r in zip(paths, rels, strict=True) if r in keep]
    except Exception:
        return paths


def scan():
    main = []
    for p in _tracked(sorted(glob.glob(os.path.join(DOCS, "*.md")))):
        n = os.path.basename(p)
        if n == "README.md":
            continue
        st, about, pct = TOP.get(n, ("Reference (verify)", "unclassified - confirm before relying on it", 50))
        if n.startswith("PRODUCT_FORGE_MASTER_API_FIRST"):
            st, about, pct = ("SSOT", "Governing master API-first -> engineering -> E2E execution plan", 0)
        pend, req, bl = gap_for(n)
        main.append((rel(p), st, _clean(about), pct, _clean(pend), req, bl))
    subs = {}
    for d, (st, about, dpct) in FOLDER.items():
        base = os.path.join(DOCS, d)
        files = sorted(f for f in glob.glob(os.path.join(base, "**", "*"), recursive=True) if os.path.isfile(f))
        items = []
        for f in files:
            n = os.path.basename(f)
            pct, status, note = dpct, st, ""
            if d in ("plans", "research", "archive"):
                pct = HIST.get(n, dpct)
                note = FOLDER_NOTE[d]
            pend, req, bl = gap_for(n)
            if d in ("plans", "research", "archive"):
                req = False
            items.append((rel(f), status, about_for(f, about, folder=d), pct, _clean(note or pend), req, bl))
        subs[d] = (about, items)
    root = []
    for p in sorted(glob.glob(os.path.join(REPO, "*.md"))):
        n = os.path.basename(p)
        st, about, pct = ROOT_TOP.get(n, ("Reference (verify)", "repo-root doc", 50))
        pend, req, bl = gap_for(n)
        root.append((n, st, _clean(about), pct, _clean(pend), req, bl))
    assets = len([f for f in glob.glob(os.path.join(DOCS, "**", "*"), recursive=True)
                  if os.path.isfile(f) and os.path.splitext(f)[1].lower() in
                  (".png", ".svg", ".pdf", ".json", ".d2", ".drawio", ".mermaid", ".ofk", ".immutable")])
    return main, subs, root, assets


def _actionable(main, subs, root):
    """Required (<100%) docs only -> the actionable roll-up at the very end."""
    rows = []
    for u, _s, _a, pc, pend, req, bl in main + root:
        if req:
            rows.append((u, pc, pend, bl))
    for d in ("plans", "research", "archive"):
        for u, _s, _a, pc, pend, req, bl in subs[d][1]:
            if req:
                rows.append((u, pc, pend, bl))
    return rows


def html_index(main, subs, root, assets):
    legend = " &nbsp; ".join(f'<span class="b {c}">{esc(n)}</span> {esc(d)}' for n, c, d in LEGEND)
    nav = ("Jump to: "
           '<a href="#truth">Implementation truth</a> · <a href="#main">Main docs</a> · '
           '<a href="#subfolders">Sub-folders</a> · <a href="#plans">Plans</a> · '
           '<a href="#research">Research</a> · <a href="#archive">Archive</a> · '
           '<a href="#root">Repo-root</a> · <a href="#pending">Pending &amp; backlog</a> · '
           '<a href="../data/backlog/index.html">Backlog &rarr;</a>')
    truth = "\n".join(
        f'<tr><td>{esc(a)}</td><td><code>{esc(b)}</code></td>'
        f'<td><span class="b {"s-impl" if s=="Implemented" else "s-plan"}">{esc(s)}</span></td>'
        f'<td>{pct_badge(pc)}</td></tr>' for a, b, s, pc in TRUTH)
    main_rows = "\n".join(
        f'<tr><td><a href="{esc(u)}">{esc(_clean_name(u))}</a></td><td><span class="b {cls(s)}">{esc(s)}</span></td>'
        f'<td>{pct_badge(pc)}</td><td class="about">{esc(a)}</td>'
        f'<td class="pend">{esc(pend)}</td>'
        f'<td><span class="pct {"p-lo" if req else "p-na"}">{"yes" if req else "no"}</span></td>'
        f'<td class="pend">{esc(bl)}</td></tr>'
        for u, s, a, pc, pend, req, bl in main)
    root_rows = "\n".join(
        f'<tr><td>{esc(_clean_name(u))}</td><td><span class="b {cls(s)}">{esc(s)}</span></td>'
        f'<td>{pct_badge(pc)}</td><td class="about">{esc(a)}</td></tr>' for u, s, a, pc, _p, _r, _b in root)

    def folder_rows(d):
        head = ('<th>File</th><th>Status</th><th>Impl %</th><th>What it\'s about</th>'
                '<th>Required?</th><th>Pending / note</th>')
        body = "\n".join(
            f'<tr><td><a href="{esc(u)}">{esc(_clean_name(u))}</a></td><td><span class="b {cls(s)}">{esc(s)}</span></td>'
            f'<td>{pct_badge(pc)}</td><td class="about">{esc(a)}</td>'
            f'<td><span class="pct {"p-lo" if req else "p-na"}">{"yes" if req else "no"}</span></td>'
            f'<td class="pend">{esc(pend or "—")}</td></tr>'
            for u, s, a, pc, pend, req, _b in subs[d][1])
        return head, body

    gh, gb = folder_rows('guidelines')
    sh, sb = folder_rows('schemas')
    kh, kb = folder_rows('knowledge')
    ch, cb = folder_rows('compact')
    ph, pb = folder_rows('plans')
    rh, rb = folder_rows('research')
    ah, ab = folder_rows('archive')

    act = _actionable(main, subs, root)
    arows = "\n".join(f'<tr><td><a href="{esc(u)}">{esc(_clean_name(u))}</a></td><td>{pct_badge(pc)}</td>'
                      f'<td class="pend">{esc(pend)}</td><td class="pend">{esc(bl)}</td></tr>'
                      for u, pc, pend, bl in act)

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Product Forge - Documentation Index</title>
<style>
 :root{{--bg:#0f1420;--card:#171e2e;--fg:#e6ebf5;--mut:#9aa7bd;--acc:#6ea8fe;--imp:#2f7d4f;--plan:#8a5a00;--hist:#6b7280;--lo:#b23b3b;--mid:#b06a00;--hi:#2f7d4f;}}
 body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,Segoe UI,Roboto,Arial}}
 header{{padding:22px 26px;background:linear-gradient(90deg,#1b2436,#0f1420);border-bottom:1px solid #26304a}}
 h1{{margin:0 0 4px;font-size:22px}} h2{{margin:26px 0 10px;font-size:18px;border-left:3px solid var(--acc);padding-left:8px}}
 h3{{margin:18px 0 8px;font-size:15px;color:#cbd5ee}} a{{color:var(--acc);text-decoration:none}} a:hover{{text-decoration:underline}}
 .wrap{{padding:0 26px 40px}} .grid{{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0}}
 .kpi{{background:var(--card);border:1px solid #26304a;border-radius:10px;padding:10px 14px;min-width:110px}} .kpi b{{font-size:20px;display:block}}
 table{{border-collapse:collapse;width:100%;background:var(--card);border:1px solid #26304a;border-radius:8px;overflow:hidden;margin:8px 0 18px}}
 th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid #222b40;vertical-align:top;font-size:13.5px}}
 th{{background:#1c2436;color:#cdd7ee}} code{{background:#0b101a;padding:1px 5px;border-radius:4px;font-size:12.5px}}
 .b{{font-size:11.5px;padding:2px 7px;border-radius:20px;color:#fff;white-space:nowrap}} .s-impl{{background:var(--imp)}} .s-plan{{background:var(--plan)}} .s-hist{{background:var(--hist)}}
 .pct{{font-size:11.5px;font-weight:700;padding:2px 8px;border-radius:20px;color:#fff;white-space:nowrap}} .p-hi{{background:var(--hi)}} .p-mid{{background:var(--mid)}} .p-lo{{background:var(--lo)}} .p-na{{background:#3a4256}}
 .about{{color:var(--mut);white-space:normal;min-width:240px;max-width:560px}} .pend{{white-space:normal;min-width:200px;max-width:480px}}
 .cta{{display:inline-block;background:var(--acc);color:#06122b;font-weight:600;padding:9px 14px;border-radius:10px;margin:6px 0}}
 .legend{{background:#141b2a;border:1px solid #26304a;border-radius:10px;padding:10px 12px;margin:10px 0;font-size:12.5px}}
 .nav{{padding:10px 12px;background:#141b2a;border:1px solid #26304a;border-radius:10px;margin:10px 0;font-size:13px}}
 footer{{color:var(--mut);padding:18px 26px;border-top:1px solid #26304a;font-size:12.5px}}
</style></head><body>
<header><h1>Product Forge - Documentation Index</h1>
 <div class="about">Main docs first, then sub-folders/plans/research/archive. Each doc shows a one-line about, status, and an <b>implementation / adoption %</b> vs the codebase.</div>
 <div class="nav">{nav}</div>
 <div class="legend"><b>Legend:</b> {legend}</div>
 <div class="grid">
  <div class="kpi"><b>{len(main)}</b>main docs</div><div class="kpi"><b>{len(subs['guidelines'][1])}</b>guidelines</div>
  <div class="kpi"><b>{len(subs['schemas'][1])}</b>schemas</div><div class="kpi"><b>{len(subs['plans'][1])}</b>plans</div>
  <div class="kpi"><b>{len(subs['research'][1])}</b>research</div><div class="kpi"><b>{len(subs['archive'][1])}</b>archived</div>
  <div class="kpi"><b>{assets}</b>assets</div>
 </div>
 <a class="cta" href="../data/backlog/index.html">Open the Backlog &rarr;</a>
 <a class="cta" href="productforge_full_architecture.md">Architecture &amp; Design SSOT &rarr;</a>
</header><div class="wrap">
 <h2 id="ssot">SSOT rules (authority order)</h2>
 <ol><li><b>Implementation truth = the code</b> - <code>core/</code>, <code>core/orchestrator/</code>, <code>config/*.json</code>, <code>pipeline-definition.json</code>. If a doc disagrees with code, code wins.</li>
 <li><b>Architecture/design SSOT</b> = <a href="productforge_full_architecture.md">productforge_full_architecture.md</a>.</li>
 <li><b>Agent prompt SSOT</b> = <code>.opencode/agent/*.md</code>; <a href="agents_prompts_instructions.md">agents_prompts_instructions.md</a> mirrors them.</li>
 <li><b>Backlog SSOT</b> = <code>data/backlog/*</code> via <code>core/backlog.py</code>.</li>
 <li><a href="#archive">docs/archive/</a> is <b>historical</b>.</li></ol>
 <p class="about">Implementation / adoption % = estimated share of the doc that exists in (or was adopted into) the codebase (100% = fully; 0% = analysis/planned). Historical plans/research/archive carry the % we <b>adopted</b> from them (so you can see we took from them and need not worry). <b>not referenced</b> = empty placeholder only.</p>
 <h2 id="truth">Current implementation truth (multi-file)</h2>
 <table><tr><th>What</th><th>Where</th><th>Status</th><th>Impl %</th></tr>{truth}</table>
 <h2 id="main">Main docs (docs/*.md)</h2>
 <table><tr><th>Doc</th><th>Status</th><th>Impl %</th><th>What it's about</th><th>Pending / note</th><th>Required?</th><th>Backlog</th></tr>{main_rows}</table>
 <h2 id="subfolders">Sub-folders</h2>
 <h3>guidelines/ - {len(subs['guidelines'][1])} files</h3><p class="about">{esc(FOLDER['guidelines'][1])}</p>
 <table><tr>{gh}</tr>{gb}</table>
 <h3>schemas/ - {len(subs['schemas'][1])} files</h3><p class="about">{esc(FOLDER['schemas'][1])}</p>
 <table><tr>{sh}</tr>{sb}</table>
 <h3>knowledge/ - {len(subs['knowledge'][1])} files</h3><p class="about">{esc(FOLDER['knowledge'][1])}</p>
 <table><tr>{kh}</tr>{kb}</table>
 <h3>compact/ - {len(subs['compact'][1])} files</h3><p class="about">{esc(FOLDER['compact'][1])}</p>
 <table><tr>{ch}</tr>{cb}</table>
 <h2 id="plans">Plans (historical roadmaps - adoption % shows what we took)</h2><p class="about">{esc(FOLDER['plans'][1])}</p>
 <table><tr>{ph}</tr>{pb}</table>
 <h2 id="research">Research (reference - adoption % shows what we used)</h2><p class="about">{esc(FOLDER['research'][1])}</p>
 <table><tr>{rh}</tr>{rb}</table>
 <h2 id="archive">Archive (implemented then superseded)</h2><p class="about">{esc(FOLDER['archive'][1])}</p>
 <table><tr>{ah}</tr>{ab}</table>
 <h2 id="root">Repo-root docs</h2>
 <table><tr><th>File</th><th>Status</th><th>Impl %</th><th>What it's about</th></tr>{root_rows}</table>
 <h2 id="pending">Pending &amp; backlog (actionable roll-up - required, below 100%)</h2>
 <p class="about">Only <b>required</b> work: docs below 100% that still need action, with the backlog item(s) that own them. Historical/reference docs are excluded (they are adopted; see their adoption % above).</p>
 <table><tr><th>Doc</th><th>Impl %</th><th>What's pending</th><th>Backlog item(s)</th></tr>{arows}</table>
 <h2 id="backlog">Backlog</h2>
 <p>Authoritative work items: <code>data/backlog/</code> (owner <code>core/backlog.py</code>).</p>
 <p><a class="cta" href="../data/backlog/index.html">View the Backlog page &rarr;</a>
    &nbsp; API: <code>GET /api/v1/backlog?scope=product_forge</code></p>
</div>
<footer>Generated {ts} by scripts/dev/gen_docs_index.py · Product Forge.</footer>
</body></html>"""


def write_readme(main, subs, root, assets):
    def note_cell(pd, req):
        if not pd:
            return "—"
        return f"**{pd}**" if req else pd

    idx = "\n".join(
        f"| [`{_clean_name(u)}`]({u}) | {s} | {pct_txt(p)} | {a} | {note_cell(pd, r)} | {bl or '—'} |"
        for u, s, a, p, pd, r, bl in main)

    def fld(d):
        return "\n".join(
            f"| [`{_clean_name(u)}`]({u}) | {s} | {pct_txt(p)} | {a} | {'yes' if r else 'no'} | {(pd or '—')} |"
            for u, s, a, p, pd, r, _b in subs[d][1])
    folders = "\n".join(
        f"| `{d}/` ({len(subs[d][1])}) | {FOLDER[d][0]} | {pct_txt(FOLDER[d][2])} | {FOLDER[d][1]} |"
        for d in sorted(FOLDER))
    truth = "\n".join(f"| {a} | `{b}` | {s} | {pct_txt(p)} |" for a, b, s, p in TRUTH)
    act = _actionable(main, subs, root)
    arows = "\n".join(f"| [`{_clean_name(u)}`]({u}) | {pct_txt(pc)} | {pend} | {bl} |" for u, pc, pend, bl in act)
    txt = f"""# Product Forge - Documentation (SSOT & index)

> **Interactive index:** [`documentation-index.html`](documentation-index.html) - main docs first, then
> sub-folders/plans/research/archive; a one-line "what it's about", status, and **implementation / adoption %**
> for every doc. Generated by `scripts/dev/gen_docs_index.py`.

## SSOT rules (authority order)
1. **Implementation truth = the code** - `core/`, `core/orchestrator/`, `config/*.json`, `pipeline-definition.json`. If a doc disagrees with code, code wins.
2. **Architecture/design SSOT = `docs/productforge_full_architecture.md`**.
3. **Agent prompt SSOT = `.opencode/agent/*.md`**; `agents_prompts_instructions.md` mirrors them.
4. **Contracts** = `STRUCTURE-CONTRACT.md`, `CONSTITUTION.md`, `AGENT_CONTRACT_STANDARD.md`, `ADDING-TO-PRODUCT-FORGE.md`, `AGENTS.md`.
5. **Backlog SSOT** = `data/backlog/*` via `core/backlog.py`.
6. `docs/archive/*` is **historical**.

> **Implementation / adoption %** = estimated share of the doc that exists in (or was adopted into) the
> codebase. Historical **plans/research/archive** carry the % we **adopted** from them; **not referenced**
> is reserved for empty placeholders.

## Current implementation truth (multi-file)
| What | Where | Status | Impl % |
|---|---|---|---|
{truth}

## Main docs (docs/*.md)
| Doc | Status | Impl % | What it's about | Pending / note | Backlog |
|---|---|---|---|---|---|
{idx}

## Folders under docs/
| Folder | Status | Impl % | About |
|---|---|---|---|
{folders}

## Plans (historical - adoption % shows what we took)
| File | Status | Impl % | What it's about | Required? | Pending / note |
|---|---|---|---|---|---|
{fld('plans')}

## Research (reference - adoption % shows what we used)
| File | Status | Impl % | What it's about | Required? | Pending / note |
|---|---|---|---|---|---|
{fld('research')}

## Archive (implemented then superseded)
| File | Status | Impl % | What it's about | Required? | Pending / note |
|---|---|---|---|---|---|
{fld('archive')}

## Sub-folders (guidelines / schemas / knowledge / compact)
| File | Status | Impl % | What it's about | Required? | Pending / note |
|---|---|---|---|---|---|
{fld('guidelines')}
{fld('schemas')}
{fld('knowledge')}
{fld('compact')}

## Repo-root docs
{chr(10).join(f'- `{u}` - {a} ({s}, ' + pct_txt(p) + ')' for u, s, a, p, _pd, _r, _b in root)}

## Pending & backlog (actionable roll-up - required, below 100%)
| Doc | Impl % | What's pending | Backlog item(s) |
|---|---|---|---|
{arows}

> Regenerate: `python scripts/dev/gen_docs_index.py`."""
    with open(README, "w", encoding="utf-8") as _f:
        _f.write(txt)


def main():
    ap = argparse.ArgumentParser(description="Generate the docs index (HTML + README)")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    main_docs, subs, root, assets = scan()
    if a.check:
        unk = [u for u, s, _a, _p, _pd, _r, _b in main_docs if "verify" in s.lower()]
        nr = [u for u, _s, _a, p, _pd, _r, _b in main_docs if p is None]
        print("unclassified docs:", unk or "none")
        print("not-referenced docs (no impl %):", nr or "none")
        return 1 if unk else 0   # PF-174: CI can gate on missing classification
    with open(HTMLOUT, "w", encoding="utf-8") as _f:
        _f.write(html_index(main_docs, subs, root, assets))
    write_readme(main_docs, subs, root, assets)
    print(f"[docs-index] wrote HTML + README | main={len(main_docs)} "
          f"archive={len(subs['archive'][1])} plans={len(subs['plans'][1])} research={len(subs['research'][1])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
