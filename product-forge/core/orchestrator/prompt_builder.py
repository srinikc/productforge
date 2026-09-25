"""
Prompt Builder (extracted from pipeline_executor - 1A.11).

Builds the standardized, agent-facing prompt scaffolding:
  - per-agent OUTPUT REQUIREMENTS (F-n / FR- / ADR- headings),
  - the tool-first DIRECTIVE (anti-exploration) for code agents,
  - the SCOPE guard that references the agreed tech stack.

Pure functions with explicit inputs so they are testable and reusable by the
executor (and any future runtime/adapter).
"""
import re
from typing import Dict, List, Optional


def _boot_test_requirement(requested_tech_stack: Optional[List[str]] = None) -> str:
    """Stack-aware boot/smoke test requirement (never framework- or path-hardcoded)."""
    blob = " ".join(str(x).lower() for x in (requested_tech_stack or []))
    if any(k in blob for k in ("fastapi", "flask", "starlette", "django", "python")):
        hint = "pytest + the framework test client (e.g. `TestClient(app)` for FastAPI/Starlette)"
    elif any(k in blob for k in ("express", "nest", "node", "next")):
        hint = "the Node test runner with an HTTP client (e.g. supertest against the server/app)"
    elif any(k in blob for k in ("go", "gin", "echo")):
        hint = "Go's `net/http/httptest` against the router/handler"
    elif any(k in blob for k in ("rust", "actix", "axum")):
        hint = "the framework's test harness for the app/router"
    elif any(k in blob for k in ("spring", "java", "kotlin")):
        hint = "the framework test harness (e.g. MockMvc / WebTestClient)"
    else:
        hint = "the stack's standard test harness"
    return ("REQUIRED BOOT TEST: add a smoke test (e.g. under `tests/smoke/`) that (1) imports the app "
            "entrypoint and (2) exercises a real request through the app's health/root route, using "
            f"{hint}. Discover the app's actual health/readiness path from its routes "
            "(e.g. /health, /healthz, /api/health, or /) — do NOT assume a fixed path or framework. "
            "This catches import/startup errors that shallow unit tests miss.\n")


def _spec_id_convention(agent_id: str = "") -> str:
    """Explicit GLOBAL vs LOCAL id convention (stops invented global windows).

    Also injects the agent's DECLARED family contract: the agent may only define the
    families registered for it (config/spec-id-families.json -> emits). Inventing a
    new prefix breaks cross-agent traceability and is a violation.
    """
    txt = ("\n\nID CONVENTION (strict):\n"
           "- GLOBAL ids (FR-, NFR-, US-): use ONLY your assigned range; they are "
           "unique across the whole spec.\n"
           "- LOCAL ids (AC-, BR-, V-, EC-, EH-, E-, API-, OQ-, ...): number them "
           "sequentially starting at 1 WITHIN this feature; they are scoped to this "
           "feature file and MAY repeat in other features. Do NOT try to make them "
           "globally unique.\n")
    try:
        from core import id_index
        emits = id_index.emits_for(agent_id) if agent_id else []
        if emits:
            txt += ("- YOUR ALLOWED id families (define ONLY these): "
                    + ", ".join(f"{p}-" for p in emits)
                    + ". Never invent a new prefix; every id you define must belong to "
                      "one of these families so cross-agent traceability can link it.\n")
        elif agent_id:
            txt += ("- You do NOT own any id family: do NOT invent or define new id "
                    "prefixes; reference existing ids only.\n")
    except Exception:
        pass
    return txt


def output_requirements(agent_id: str, requested_tech_stack: Optional[List[str]] = None,
                        allocation: Optional[Dict] = None) -> str:
    """Strict output requirements so downstream parsing/verification works.

    `allocation` (per-feature -> FR/NFR/US ranges) is injected for the
    per-feature spec agents so ids can never be invented or collide.
    """
    _alloc = ""
    if allocation:
        try:
            from core.agent_requirements import format_allocation_table
            _alloc = format_allocation_table(allocation)
        except Exception:
            _alloc = ""
    if agent_id == "ideation":
        return ("\n\nOUTPUT REQUIREMENTS:\nUse exactly these headings:\n# Vision\n"
                "# Target Users / Personas\n# E2E Workflow / User Journey\n# Features\n"
                "# Success Criteria\n# Risk Assessment\n"
                "Under # Features list each feature as: "
                "- **F-1: <name> (must-have):** <description>. "
                "Label every feature must-have or nice-to-have.")
    if agent_id == "product-design-spec":
        return ("\n\nOUTPUT REQUIREMENTS:\nProduce a PER-FEATURE DESIGN spec (the HOW). For EVERY feature id "
                "(F-1, F-2, ... from the product plan) emit a section titled '## F-<n>: <name>' containing ALL of:\n"
                "- Links: FR-<n>, NFR-<n>, US-<n> (use the REAL ids from this design's FR/NFR/US lists; "
                "NEVER write `FR: F-<n>` and never reuse the feature id as a requirement id)\n"
                "- Screens + components (with states: empty / loading / error / success)\n"
                "- Flows: user flow + system flow\n"
                "- Diagrams: MUST be fenced with the language tag — use ```mermaid blocks for state machine "
                "(stateDiagram-v2), user flow (flowchart), sequence diagram (sequenceDiagram), ER/data model (erDiagram)\n"
                "- API contracts: endpoints, request/response, status codes\n"
                "- Data model: entities, fields, constraints\n"
                "- Per-feature NFRs (performance, security) + accessibility (WCAG 2.1 AA)\n"
                "- Test plan: unit/api/integration/e2e/a11y, each traced to the feature id\n"
                "- Definition of Done\n"
                "Then an APPENDIX with global Screens/Flows/Components/States/Data + API Contracts + Test Plan "
                "+ Traceability. No placeholders. Do NOT omit features.\n"
                "Also include a '## Diagrams (draw.io + SVG/PDF)' appendix listing each diagram's id so the "
                "pipeline renders .drawio and PDF." + _spec_id_convention(agent_id)) + _alloc
    if agent_id == "design":
        return ("\n\nOUTPUT REQUIREMENTS (per-feature FUNCTIONAL spec):\n"
                "Produce a PER-FEATURE FUNCTIONAL specification (the WHAT it must do). For EVERY feature id "
                "(F-1, F-2, ... from the product plan) emit a section titled '## F-<n>: <name>' containing ALL of:\n"
                "- Requirements: FR-<n>, NFR-<n>, US-<n> ids (REAL ids; never reuse the feature id as a "
                "requirement id)\n"
                "- Behaviour (what it must do)\n"
                "- Business rules\n"
                "- Validation\n"
                "- Edge cases\n"
                "- Error handling\n"
                "- Acceptance criteria\n"
                "- API behaviour\n"
                "- Priority (must-have / should-have / nice-to-have)\n"
                "Then the global sections: ## Functional Requirements (FR-1, FR-2, ...), "
                "## Non-Functional Requirements (NFR-1, ...; cover performance, scalability/availability, "
                "security, data/residency, deployment/environment), ## User Stories "
                "(US-1: As a ... I want ... so that ...), ## API Contracts.\n"
                "No placeholders. Do NOT omit features." + _spec_id_convention(agent_id)) + _alloc
    if agent_id == "architect":
        req = ", ".join(requested_tech_stack or []) or "none (you decide)"
        return ("\n\nOUTPUT REQUIREMENTS:\nYou MUST include EVERY one of these headings "
                "(do not omit any):\n## Architecture Style, ## Tech Stack, "
                "## Components, ## File Structure, ## Data / Database (Entities), "
                "## Deployment / Infrastructure, ## Integration Points, ## Security Considerations, "
                "## ADRs\n(list each as ADR-1, ...)\n"
                f"USER-REQUESTED TECH STACK (constraint): {req}.\n"
                "You are the architect: choose the RIGHT stack for this product. If you change the "
                "requested stack, you MUST justify it (rationale + trade-offs).\n"
                "BE CONCISE: bullet lists, total <= ~1200 words; keep ADRs to <=5 and one line each. "
                "Emit EVERY heading above even if brief — do not let any section be cut off.\n"
                "Also output EXACTLY ONE fenced ```json block describing the decision with keys: "
                "kind (cli|library|web-app|api|mobile|service), languages, frameworks, database, "
                "cache, deploy, runtime, requested (list), changed_from_request (bool), rationale.\n"
                "Then output a SECOND fenced ```json block for infrastructure with keys: "
                "compute, storage, networking, identity, observability, environments, vendors (list; "
                "use 'unknown'/'user_to_provide' if not certain), packaging, deploy, unknowns (list), rationale.")
    if agent_id.startswith("implement") or agent_id in ("devops", "fix"):
        return ("\n\nIMPORTANT — ACTUAL FILES REQUIRED:\nYou MUST use the write_file tool to create "
                "real files in the project workspace (e.g. src/..., tests/...). Do NOT just describe "
                "code. After writing, run tests with run_command where applicable, then give a short "
                "final summary. No mocks, no TODOs, no placeholders.\n"
                "PATHS: write paths RELATIVE to the current working directory (e.g. `src/app.py`, "
                "`tests/test_app.py`) — do NOT prefix `products/<project>/` (you are already in it).\n"
                "TEST LOCATIONS: place layer tests in the catalogue dirs — `tests/unit/`, `tests/db/`, "
                "`tests/api/`, `tests/integration/` (create them) — so layer/coverage gates pass.\n"
                + _boot_test_requirement(requested_tech_stack) +
                "TEST TRACEABILITY: in every test you write, tag the requirement it verifies with a "
                "comment/name containing its id (e.g. `# FR-1`, `# NFR-2`, `def test_fr_1_...`).")
    if agent_id == "validate":
        return ("\n\nIMPORTANT:\nUse run_command to actually run the test suite in the workspace and "
                "report the real results. If tests are missing or failing, say so explicitly.\n"
                "Ensure tests reference requirement ids (FR-/NFR-) so traceability can be computed.")
    if agent_id in ("ux-ia", "design", "architect"):
        return ("\n\nOUTPUT REQUIREMENTS (design tokens):\nAlso write `docs/uiux-theme.md` (5.6) with "
                "concrete design tokens: color palette (hex), typography scale, spacing scale, "
                "radius/shadow, component states (default/hover/active/disabled/focus), and "
                "accessibility notes (WCAG AA). Downstream UI agents consume these tokens.")
    if agent_id == "document":
        return ("\n\nOUTPUT REQUIREMENTS (docs):\nProduce real files: `docs/INSTALL.md` (9.1), "
                "`docs/USER_GUIDE.md` (9.2), `docs/API_GUIDE.md` (9.3) when the product has an API, "
                "plus `README.md`. Include exact commands, prerequisites, configuration, and examples. "
                "No placeholders.")
    if agent_id == "implement-ui":
        return ("\n\nUI REQUIREMENTS (9.4):\nProvide in-app guidance: empty states, loading states, "
                "and contextual help/tooltips for each screen. Include error states with actionable text.")
    # ── Phase 1.5 / 7 business agents: refer to the business-models KB (BI-0119) ──
    if agent_id in ("product-owner", "pricing-strategist", "marketing", "growth",
                    "customer-success", "community-social", "sales-crm",
                    "legal-privacy", "product-analytics", "observer"):
        kb_hint = ""
        try:
            from core import business_models_kb as _kb
            secs = ", ".join(_kb.sections())
            kb_hint = ("\nREFER TO THE BUSINESS-MODELS KB (config/business-models-kb.json): "
                       "you have sections " + secs + ". Ground models/pricing/unit-economics/GTM/growth "
                       "choices in it and cite the entry id. If a model/skill you need is ABSENT, say so "
                       "explicitly and flag it as `needs_research` (it will be learned, not invented).")
        except Exception:
            kb_hint = ""
        return ("\n\nOUTPUT REQUIREMENTS (business agent):\nProduce a role-appropriate artifact with "
                "explicit sections, defined metrics/assumptions, and sourced reasoning. State every "
                "assumption; never fabricate market numbers. Mark estimates as estimates." + kb_hint)
    return ""


_RESEARCH_AGENTS = {"researcher", "scout"}


def research_guard(agent_id: str) -> str:
    """Keep research concise; allow splitting long notes into multiple files."""
    if agent_id not in _RESEARCH_AGENTS:
        return ""
    return ("\n\nRESEARCH OUTPUT — BE A CONCISE BRIEF (not an essay):\n"
            "- Bullet points, facts only, cite sources inline. Target <= ~600 words.\n"
            "- If you need more space, write MULTIPLE short files under `docs/research/` "
            "(e.g. part-1.md, part-2.md) via write_file instead of one huge document.\n"
            "- Mark anything uncertain as 'unknown' rather than guessing.")


def tool_directive(agent_id: str, stage_id: str, task: str, enable_tools: bool, project: str) -> str:
    """Strong override prepended for tool-using agents (anti-exploration)."""
    if not (enable_tools and (agent_id.startswith("implement")
                              or agent_id in ("devops", "fix", "validate"))):
        return ""
    lines = [
        "CRITICAL DIRECTIVES (highest priority — these override everything below):",
        "- You are a SINGLE agent. IGNORE any instruction about a 'Task' tool or sub-agents.",
        "- Create real files with the write_file tool. Do NOT call list_dir/read_file just to explore.",
    ]
    if agent_id.startswith("implement") or agent_id in ("devops", "fix"):
        pkg = re.sub(r"[^a-z0-9_]", "_", (project or "app").lower())
        lines += [
            "- Start writing files IMMEDIATELY with write_file. If the workspace is empty, first create a",
            "  minimal runnable skeleton: src/<package>/__init__.py, src/<package>/main.py,",
            "  tests/test_<name>.py, requirements.txt.",
            f"- Use ONE Python package named '{pkg}' (files under src/{pkg}/). Do NOT create other",
            f"  top-level packages. Tests go in tests/test_{pkg}.py.",
            "- Implement in STRICT layer order (dependency-first): "
            "(1) DB/schema/migrations, (2) business logic/domain, (3) API/endpoints, (4) UI, "
            "(5) integration wiring. Do not start a layer before the layer it depends on is written.",
            "- Then implement the task/features by writing or overwriting files.",
            "- No mocks, no TODOs, no placeholders. Use run_command with `python -c \"...\"` when needed",
            "  (do NOT use `ls`/`dir`/`cat` — they are not available).",
        ]
    if agent_id == "validate":
        lines += ["- Use run_command to actually run `python -m pytest -q` and report the real results."]
    return "\n".join(lines)


def conciseness_guard(agent_id: str) -> str:
    """Common anti-truncation guard for long-document agents (config-driven)."""
    try:
        from core.agent_requirements import is_verbose
        verbose = is_verbose(agent_id)
    except Exception:
        verbose = agent_id in {"ideation", "discovery", "design", "architect",
                               "product-design-spec", "document"}
    if verbose:
        return ("\n\nCOMPLETENESS & LENGTH: Keep the document concise (bullet lists, no repetition, "
                "no restating the same point). Include EVERY required section (even if brief); "
                "never let a section be cut off.")
    return ""


_INFRA_AGENTS = {"design", "architect"}


def infra_awareness_guard(agent_id: str) -> str:
    """Make design/architect infra/deploy/vendor-aware and pick 'research vs ask'."""
    if agent_id not in _INFRA_AGENTS:
        return ""
    return ("\n\nINFRASTRUCTURE & DEPLOYMENT AWARENESS:\n"
            "- Cover COMPUTE (cpu/gpu/autoscale/regions), STORAGE (object/block/file/DB/cache/"
            "search/vector/queue), NETWORKING (vpc/subnet/dns/lb/ingress/tls/cdn/api-gateway/ports), "
            "IDENTITY/SECURITY (iam/secrets/kms), OBSERVABILITY (logs/metrics/traces/slo), "
            "ENVIRONMENTS (dev/stage/prod), DATA/COMPLIANCE (residency/retention/backup/dr).\n"
            "- Cover PACKAGING (image/wheel/jar/msi-deb-rpm/apk-ipa/bundle) and DEPLOY target "
            "(docker/kubernetes/terraform/ansible/paas/serverless/vendor appliance).\n"
            "- Vendor specifics (Dell/HP/IBM/Cisco/VMware/cloud/storage vendors): if you are NOT certain, "
            "do NOT invent them. Mark them 'unknown'/'user_to_provide' and RECOMMEND a research step "
            "(web search + knowledge base + skills). Ask the user (HITL) for environment/credentials/lab details.\n"
            "- Derive infra from the product KIND + requirements/NFRs; keep it minimal for simple products.")


def scope_guard(tech_stack: Optional[Dict], requested_tech_stack: Optional[List[str]]) -> str:
    """Remind the agent of the agreed tech stack (no hardcoded stack)."""
    chosen = (tech_stack or {}).get("chosen") or {}
    if chosen:
        desc = (f"kind={chosen.get('kind')}, languages={chosen.get('languages')}, "
                f"frameworks={chosen.get('frameworks') or []}")
        return ("\n\nSCOPE & TECH STACK (MUST follow docs/tech-stack.json): " + desc +
                ". Do NOT add frameworks, databases, servers, authentication, or a UI not listed there.")
    hints = ", ".join(requested_tech_stack or []) or "unspecified"
    return ("\n\nSCOPE & TECH STACK (MUST follow): " + hints +
            ". Do NOT introduce frameworks/DB/auth/UI beyond the request unless the brief requires it.")
