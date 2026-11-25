"""Seed the Unified Agent Memory Platform epic + children (idempotent) via the backlog API.

Design: docs/Product_Forge_Agent_Memory_Architecture_Integration.md
Related SSOTs:
  - docs/RAG-PROCESS-MEMORY.md
  - docs/SCOPED-LEARNINGS-DESIGN.md
  - docs/CORRECTION-LEDGER.md
  - docs/Product_Forge_Enterprise_Performance_Security_DB_Storage_Roadmap.md

Run from the product-forge root:
  $env:PF_GROOMING_AI="0"; $env:PF_BACKLOG_DB="off"; python scripts/dev/seed_agent_memory_backlog.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core import backlog  # noqa: E402

S = "product_forge"
P = None
SRC = "design:Product_Forge_Agent_Memory_Architecture_Integration.md"
EXTERNAL = "agent-memory-platform"

UNIVERSAL_DOD = [
    "Feature branch off develop (never commit to develop/main directly).",
    "Code review of the diff; findings fixed.",
    "Lint/static clean (scripts/dev/lint_check.py).",
    "language_rule_check PASS - new logic in Go (go/pfcore/*.go, go/pfmemory/*.go), edits to existing shipped Python only.",
    "precheck PASS (compileall, wired_audit, api/governance, engineering-flow, backlog-e2e, docs-fresh, secret-scan, pipeline tests).",
    "Evidence (artifact + test descriptors) linked on this item; intent_trace resolves.",
    "Merged to develop immediately after green; delivery provenance recorded (branch, merge_sha, pr).",
]


def body(problem, goal, in_scope, out_scope, dod, references=None):
    def sec(title, lines):
        return f"## {title}\n" + "\n".join(f"- {x}" for x in lines) + "\n"
    ref_sec = ""
    if references:
        ref_sec = "## Reference Documents\n" + "\n".join(f"- `{r}`" for r in references) + "\n\n"
    return (
        f"## Problem / why\n{problem}\n\n"
        f"## Goal & value\n{goal}\n\n"
        + ref_sec
        + sec("In scope", in_scope) + "\n"
        + sec("Out of scope", out_scope) + "\n"
        + sec("Definition of Done", dod) + "\n"
        + "## Verification\nStructured `acceptance_criteria` is the single source of truth for verification.\n"
    )


EPIC = {
    "ext": f"{EXTERNAL}:epic",
    "title": "EPIC: Unified Agent Memory Platform (6-Type Memory Model, Lifecycle, and Consolidation)",
    "problem": (
        "Agent memory in Product Forge is currently fragmented across JSON files, ad-hoc execution state, and ephemeral "
        "model context windows. Agents repeatedly forget user instructions across turns, repeat known failure patterns, "
        "falsely claim tasks are completed without verifying evidence, and suffer from memory pollution where historical "
        "or cross-project context contaminates current active runs."
    ),
    "goal": (
        "Implement the Unified Agent Memory Architecture from docs/Product_Forge_Agent_Memory_Architecture_Integration.md. "
        "Formalize the 6 canonical memory types (Working, Semantic, Episodic, Procedural, Prospective, External/Retrieval) "
        "behind a central Memory Orchestrator, Compiler, Consolidator, and strict Governance framework with zero cross-tenant "
        "leakage, explicit supersession, and verified post-run knowledge promotion."
    ),
    "in_scope": [
        "Canonical Memory Record contract & 6-type taxonomy schema.",
        "Central Memory Orchestrator with scope isolation and ACL enforcement.",
        "Memory Compiler with agent-persona retrieval policies (Coding, QA, Security).",
        "Memory Consolidator distilling verified episodic runs into semantic/procedural patterns.",
        "Memory Governance, provenance lineage, temporal validity, and explicit supersession.",
        "Prospective Memory engine tracking deferred obligations and follow-up commitments.",
        "Memory graph relationships and observability dashboard.",
    ],
    "out_scope": [
        "Rewriting existing core pipeline orchestrators from scratch.",
        "Unverified automatic promotion of failed run traces to authoritative knowledge.",
        "Cross-tenant memory sharing without explicit legal consent/tenant federation.",
    ],
    "ac": [
        "Unified memory model classifies all memories into 6 canonical types with type-safe schemas.",
        "Memory Orchestrator acts as single gateway with proven zero cross-tenant / cross-project data leakage.",
        "Memory Compiler tailors memory injection by agent role (Coding, QA, Security) under strict token limits.",
        "Memory Consolidator promotes only verified execution outcomes into permanent semantic/procedural memory.",
        "Superseded and expired memories are deterministically excluded from active agent prompts while retaining audit history.",
        "Prospective Memory reliably tracks and surfaces deferred commitments across agent session resets.",
        "Memory observability APIs provide complete provenance tracing for every injected memory record.",
    ],
    "dod": [
        "Epic architecture and component interfaces approved at Gate 1.",
        "All child features delivered with 0 blockers / 0 majors.",
    ],
    "value": 5, "effort": 4, "risk": 2, "moscow": "Must",
    "references": [
        "docs/Product_Forge_Agent_Memory_Architecture_Integration.md",
        "docs/RAG-PROCESS-MEMORY.md",
        "docs/SCOPED-LEARNINGS-DESIGN.md",
        "docs/CORRECTION-LEDGER.md",
        "docs/Product_Forge_Enterprise_Performance_Security_DB_Storage_Roadmap.md",
    ],
}

ITEMS = [
    {
        "ext": f"{EXTERNAL}:record-contract-taxonomy",
        "title": "Canonical Memory Record Contract: schema definition, 6-type taxonomy classification, and storage mapping",
        "problem": "Memory records have inconsistent schemas across JSON files, database tables, and runtime caches with no standard taxonomy.",
        "goal": "Define the standard MemoryRecord contract and classify all memory assets into the 6 canonical types (Working, Semantic, Episodic, Procedural, Prospective, External).",
        "in_scope": [
            "MemoryRecord schema (id, tenant_id, project_id, kind, scope, authority_tier, provenance, confidence, valid_from, valid_until, superseded_by, embedding, payload_ref).",
            "Type-safe schema validators for all 6 memory kinds.",
            "Backward-compatible mapping layer from existing core/agent_memory.py categories.",
        ],
        "out_scope": ["Bespoke unversioned JSON structures."],
        "ac": [
            "AC-1: Standard MemoryRecord schema implemented in Go and Python with strict field validation.",
            "AC-2: Validates memory kinds against the canonical 6 types (unknown kinds fail closed).",
            "AC-3: Existing 8 types in core/agent_memory.py map cleanly into the canonical schema.",
            "AC-4: Temporal validity (valid_from, valid_until) is strictly validated.",
        ],
        "dod": ["Contract and validation unit tests pass with 100% field coverage."],
        "files": ["core/memory_record.py", "go/pfmemory/record.go", "go/pfmemory/record_test.go"],
        "value": 4, "effort": 3, "risk": 1, "moscow": "Must", "deps": [],
        "references": ["docs/Product_Forge_Agent_Memory_Architecture_Integration.md#section-4", "docs/Product_Forge_Agent_Memory_Architecture_Integration.md#section-10"],
    },
    {
        "ext": f"{EXTERNAL}:memory-orchestrator",
        "title": "Memory Orchestrator: unified memory read/write gateway, multi-tenant isolation, ACL enforcement, and scope filtering",
        "problem": "Direct database queries and file reads bypass security checks, risking cross-tenant memory leakage and inconsistent writes.",
        "goal": "Build the central Memory Orchestrator as the single governed gateway for all memory operations with strict tenant and project ACL enforcement.",
        "in_scope": [
            "Unified gateway interface (Put, Get, Search, Delete, Validate, Consolidate).",
            "Multi-tenant isolation and Row-Level Security (RLS) enforcement.",
            "Project and user ACL boundary checks.",
            "Negative penetration tests verifying zero cross-tenant leakage.",
        ],
        "out_scope": ["Direct bypass of the orchestrator by individual agent workers."],
        "ac": [
            "AC-1: Memory Orchestrator intercepts and validates all memory reads, writes, and searches.",
            "AC-2: SQL/storage filters guarantee zero cross-tenant and cross-project data leakage.",
            "AC-3: Four negative leakage test suites verify boundary isolation under concurrent load.",
        ],
        "dod": ["Leakage penetration tests pass with zero cross-boundary exposure."],
        "files": ["core/memory_orchestrator.py", "go/pfmemory/orchestrator.go", "go/pfmemory/orchestrator_test.go"],
        "value": 5, "effort": 3, "risk": 2, "moscow": "Must", "deps": ["record-contract-taxonomy"],
        "references": ["docs/Product_Forge_Agent_Memory_Architecture_Integration.md#section-7", "docs/Product_Forge_Agent_Memory_Architecture_Integration.md#section-14"],
    },
    {
        "ext": f"{EXTERNAL}:memory-compiler",
        "title": "Memory Compiler: persona-specific retrieval profiles (Coding, QA, Security), relevance ranking, and context injection",
        "problem": "All agents receive generic memory injections, resulting in irrelevant context, noisy prompts, and missed role-specific constraints.",
        "goal": "Implement the Memory Compiler to assemble persona-specific memory contexts (Coding, QA, Security) under strict token budget constraints.",
        "in_scope": [
            "Persona-specific retrieval policies (weights per memory kind, similarity thresholds, recency decay).",
            "Context assembly pipeline producing auditable prompt snippets.",
            "Relevance filtering suppressing noise and outdated execution traces.",
        ],
        "out_scope": ["Unbounded memory injection without token limits."],
        "ac": [
            "AC-1: Coding agent receives ADRs, code standards, and active design decisions.",
            "AC-2: QA agent receives test criteria, known defect patterns, and historical failure traces.",
            "AC-3: Security agent receives threat models, policy rules, and vulnerability ledgers.",
            "AC-4: Compiled context conforms strictly to allocated token budgets.",
        ],
        "dod": ["Compiler tests verify distinct, role-tailored memory snippets for each agent persona."],
        "files": ["core/memory_compiler.py", "go/pfmemory/compiler.go", "go/pfmemory/compiler_test.go"],
        "value": 4, "effort": 3, "risk": 2, "moscow": "Must", "deps": ["memory-orchestrator"],
        "references": ["docs/Product_Forge_Agent_Memory_Architecture_Integration.md#section-8", "docs/Product_Forge_Agent_Memory_Architecture_Integration.md#section-15"],
    },
    {
        "ext": f"{EXTERNAL}:memory-consolidator",
        "title": "Memory Consolidator: post-execution distillation, episodic trace distillation into semantic/procedural patterns, and failure promotion guards",
        "problem": "Failed or unverified agent outputs pollute memory, causing agents to hallucinate falsehoods or repeat buggy code patterns.",
        "goal": "Build the Memory Consolidator to distill verified execution outcomes into lasting semantic and procedural memory while gating unverified traces.",
        "in_scope": [
            "Post-execution distillation pipeline.",
            "Verification gate: only runs passing verification/tests can be promoted to authoritative memory.",
            "Pattern extractor converting episodic run logs into reusable procedural skills.",
            "Deduplication merging redundant run observations.",
        ],
        "out_scope": ["Automatic promotion of unverified agent claims or failed runs."],
        "ac": [
            "AC-1: Failed runs are marked as failure lessons/anti-patterns, never as successful procedures.",
            "AC-2: Successful runs with passing tests distill reusable patterns into procedural memory.",
            "AC-3: Deduplication clusters similar observations and updates existing knowledge entries.",
        ],
        "dod": ["Consolidation test verifies that simulated failed runs never promote to authoritative procedures."],
        "files": ["core/memory_consolidator.py", "go/pfmemory/consolidator.go", "go/pfmemory/consolidator_test.go"],
        "value": 4, "effort": 3, "risk": 2, "moscow": "Must", "deps": ["memory-orchestrator"],
        "references": ["docs/Product_Forge_Agent_Memory_Architecture_Integration.md#section-9", "docs/Product_Forge_Agent_Memory_Architecture_Integration.md#section-26"],
    },
    {
        "ext": f"{EXTERNAL}:governance-supersession-lifecycle",
        "title": "Memory Governance & Lifecycle: explicit supersession tracking, temporal expiration, validity windows, and audit logging",
        "problem": "Old decisions and stale rules linger indefinitely in memory, conflicting with newer architecture and misleading agents.",
        "goal": "Implement full lifecycle governance for memory records with explicit supersession, temporal expiration, and complete mutation audit trails.",
        "in_scope": [
            "Supersession mechanism (superseded_by pointer, status=superseded).",
            "Temporal validity engine filtering out expired records (valid_until < now).",
            "Cryptographic provenance linking each memory to commit SHA, run ID, or operator decision.",
            "Append-only audit log of memory creation, updates, and supersession.",
        ],
        "out_scope": ["Hard-deleting historical memories without audit preservation."],
        "ac": [
            "AC-1: Updating a memory supersedes the prior version without deleting historical audit trail.",
            "AC-2: Active queries automatically filter out superseded and expired memory records.",
            "AC-3: Every memory record maintains full provenance back to source artifact or gate decision.",
        ],
        "dod": ["Lifecycle tests prove superseded records are never injected as active authority."],
        "files": ["core/memory_governance.py", "go/pfmemory/governance.go", "go/pfmemory/governance_test.go"],
        "value": 4, "effort": 3, "risk": 1, "moscow": "Must", "deps": ["record-contract-taxonomy"],
        "references": ["docs/Product_Forge_Agent_Memory_Architecture_Integration.md#section-11", "docs/Product_Forge_Agent_Memory_Architecture_Integration.md#section-12"],
    },
    {
        "ext": f"{EXTERNAL}:prospective-memory-engine",
        "title": "Prospective Memory Engine: tracking deferred actions, future stage obligations, scheduled triggers, and cross-stage handoff notes",
        "problem": "Agents lose track of deferred obligations, follow-up commitments, and cross-stage handoff notes across restarts.",
        "goal": "Deliver the Prospective Memory engine to track deferred actions, trigger conditions, and cross-stage obligations so agents never drop commitments.",
        "in_scope": [
            "Prospective obligation schema (action, trigger_condition, target_stage, status, priority).",
            "Trigger evaluation engine firing on workflow state transitions or gate take-ups.",
            "Cross-stage handoff compiler re-injecting pending commitments at the next stage start.",
        ],
        "out_scope": ["Unchecked background daemon execution without workflow orchestration."],
        "ac": [
            "AC-1: Records deferred commitments with structured trigger conditions.",
            "AC-2: Automatically surfaces pending obligations when entering target stage or gate.",
            "AC-3: Marks obligations as fulfilled upon verified completion or explicit dismissal.",
        ],
        "dod": ["End-to-end stage handoff test verifies prospective obligations persist and trigger across runs."],
        "files": ["core/prospective_memory.py", "go/pfmemory/prospective.go", "go/pfmemory/prospective_test.go"],
        "value": 4, "effort": 3, "risk": 1, "moscow": "Should", "deps": ["memory-orchestrator"],
        "references": ["docs/Product_Forge_Agent_Memory_Architecture_Integration.md#section-5.6", "docs/RAG-PROCESS-MEMORY.md#section-9"],
    },
    {
        "ext": f"{EXTERNAL}:memory-graph-observability",
        "title": "Memory Graph & Observability: relationship linking (derived_from, contradicts, reinforces), memory audit trail, and retrieval inspection API",
        "problem": "Operators cannot inspect what memories an agent accessed, why a memory was chosen, or how memories relate to each other.",
        "goal": "Build the Memory Graph and observability API providing full inspection of memory relationships, retrieval reasoning, and audit traces.",
        "in_scope": [
            "Relationship graph (derived_from, supersedes, contradicts, reinforces).",
            "Trace inspection API returning full memory context for any run ID.",
            "Observability metrics for retrieval latency, cache hits, and memory volume.",
        ],
        "out_scope": ["Heavy external graph database clusters."],
        "ac": [
            "AC-1: Models directed relationships between memory records, code artifacts, and decisions.",
            "AC-2: Inspection API returns complete memory provenance for any given run execution trace.",
            "AC-3: Real-time telemetry exports memory retrieval counts, latencies, and token expenditures.",
        ],
        "dod": ["Trace inspection API tests pass with full lineage reconstruction of sample runs."],
        "files": ["core/memory_graph.py", "go/pfmemory/graph.go", "go/pfmemory/observability.go"],
        "value": 3, "effort": 3, "risk": 1, "moscow": "Should", "deps": ["memory-compiler", "governance-supersession-lifecycle"],
        "references": ["docs/Product_Forge_Agent_Memory_Architecture_Integration.md#section-28", "docs/Product_Forge_Agent_Memory_Architecture_Integration.md#section-31"],
    },
]

WAVES = {
    "record-contract-taxonomy": 1,
    "memory-orchestrator": 1,
    "memory-compiler": 2,
    "memory-consolidator": 2,
    "governance-supersession-lifecycle": 3,
    "prospective-memory-engine": 3,
    "memory-graph-observability": 4,
}

API_IMPACT = {
    "epic": "coordination epic; delivered through internal Go/Python memory and orchestrator surfaces",
    "record-contract-taxonomy": "internal contract models; schema definitions in Go/Python",
    "memory-orchestrator": "extends /memory API; internal gateway for agent workers",
    "memory-compiler": "internal agent runner context compilation API",
    "memory-consolidator": "background post-execution distillation service; no public HTTP route",
    "governance-supersession-lifecycle": "internal lifecycle and validation ops",
    "prospective-memory-engine": "internal workflow trigger and handoff API",
    "memory-graph-observability": "inspection endpoint GET /memory/trace/{run_id}",
}


def _should_write(ext: str, prior_ext: set, existing_deps: list | None) -> bool:
    return ext not in prior_ext or not existing_deps


def main() -> int:
    prior_ext = {e.get("external_id") for e in backlog.list_open(S, P) + backlog.list_closed(S, P)}
    epic = backlog.add_epic(
        S, P, EPIC["title"],
        body=body(EPIC["problem"], EPIC["goal"], EPIC["in_scope"], EPIC["out_scope"], EPIC["dod"], EPIC["references"]),
        type_="epic", origin="review", source=SRC, external_id=EPIC["ext"],
        value=EPIC["value"], effort=EPIC["effort"], risk=EPIC["risk"], moscow=EPIC["moscow"],
        acceptance_criteria=EPIC["ac"],
    )
    epic_id = epic["id"]
    if EPIC["ext"] not in prior_ext:
        backlog.update(S, P, epic_id, api_impact={
            "needs_api": False, "routes": [], "consumers": [], "reason": API_IMPACT["epic"]})
    print(f"epic {epic_id}: {epic['title']}")

    created = {}
    for it in ITEMS:
        full_dod = it["dod"] + UNIVERSAL_DOD
        row = backlog.add_epic(
            S, P, it["title"],
            body=body(it["problem"], it["goal"], it["in_scope"], it["out_scope"], it["dod"], it["references"]),
            type_="feature", origin="review", source=SRC, external_id=it["ext"], epic=str(epic_id),
            value=it["value"], effort=it["effort"], risk=it["risk"], moscow=it["moscow"],
            acceptance_criteria=it["ac"],
        )
        created[it["ext"].split(":")[-1]] = row["id"]
        if it["ext"] not in prior_ext:
            backlog.update(
                S, P, row["id"], affected_files=it["files"], verification=full_dod,
                api_impact={"needs_api": False, "routes": [], "consumers": [],
                            "reason": API_IMPACT[it["ext"].split(":")[-1]]},
                _note="planned affected files + DoD (design)")
        print(f"  {row['id']:12} {it['title']}")

    for it in ITEMS:
        eid = created[it["ext"].split(":")[-1]]
        deps = [{"task_id": created[d], "type": "REQUIRES", "required_state": "completed"}
                for d in it["deps"]]
        if deps and _should_write(it["ext"], prior_ext, (backlog.get(S, P, eid) or {}).get("dependencies")):
            backlog.set_dependencies(S, P, eid, dependencies=deps)

    prior_order = {r.get("id"): r for r in (backlog.get(S, P, epic_id) or {}).get("execution_order", [])}

    def _wave(k: str) -> int:
        prior = prior_order.get(created[k]) or {}
        w = prior.get("wave")
        return w if isinstance(w, int) and w > 0 else WAVES[k]

    order = []
    for k in sorted(created, key=lambda x: (_wave(x), WAVES[x])):
        eid = created[k]
        prior = prior_order.get(eid) or {}
        order.append({"id": eid, "wave": _wave(k), "status": prior.get("status", "new")})
    backlog.set_execution_order(S, P, epic_id, order)
    print(f"execution order set on {epic_id}: {len(order)} items across {max(WAVES.values())} waves")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
