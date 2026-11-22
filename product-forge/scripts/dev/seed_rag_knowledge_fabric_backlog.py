"""Seed the RAG, CAG & Governed Knowledge Fabric epic + children (idempotent) via the backlog API.

Design: docs/Product_Forge_RAG_CAG_Knowledge_Fabric_Integration.md
Related SSOTs:
  - docs/RAG-PROCESS-MEMORY.md
  - docs/EDP-STORE-STATUS-AND-CONCURRENCY.md
  - docs/Product_Forge_Enterprise_Performance_Security_DB_Storage_Roadmap.md

Run from the product-forge root:
  $env:PF_GROOMING_AI="0"; $env:PF_BACKLOG_DB="off"; python scripts/dev/seed_rag_knowledge_fabric_backlog.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core import backlog  # noqa: E402

S = "product_forge"
P = None
SRC = "design:Product_Forge_RAG_CAG_Knowledge_Fabric_Integration.md"
EXTERNAL = "rag-cag-knowledge-fabric"

UNIVERSAL_DOD = [
    "Feature branch off develop (never commit to develop/main directly).",
    "Code review of the diff; findings fixed.",
    "Lint/static clean (scripts/dev/lint_check.py).",
    "language_rule_check PASS - new logic in Go (go/pfcore/*.go, go/pfrag/*.go), edits to existing shipped Python only.",
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
    "title": "EPIC: RAG, CAG & Governed Knowledge Fabric (Unified Retrieval & Context Substrate)",
    "problem": (
        "Product Forge lacks a unified knowledge layer. RAG, CAG, and knowledge management risk becoming three "
        "disconnected silos. Currently, agents suffer from naive global broadcasts, context window bloat, missing token "
        "budgeting, lack of provenance, and conflicting knowledge injections across turns."
    ),
    "goal": (
        "Implement the unified, governed Knowledge Fabric, Cache-Augmented Generation (CAG), and hybrid RAG architecture "
        "from docs/Product_Forge_RAG_CAG_Knowledge_Fabric_Integration.md. Provide intelligent routing across prompt "
        "context, pre-computed cache, vector search, BM25 keyword search, and knowledge graphs with strict token budgeting, "
        "cryptographic provenance, and authority hierarchy enforcement."
    ),
    "in_scope": [
        "Dynamic Context and Knowledge Router.",
        "Governed Knowledge Fabric registry with schema validation and provenance.",
        "Pluggable hybrid retrieval (Vector + BM25 + Graph) with Reciprocal Rank Fusion (RRF) and reranking.",
        "CAG context-caching layer with deterministic invalidation hooks.",
        "Context and Prompt Compiler with strict per-stage token budgeting.",
        "Knowledge authority and conflict resolution engine (SSOT > ADR > Decision > Learned).",
        "Comprehensive retrieval and context evaluation harness.",
    ],
    "out_scope": [
        "External proprietary vector databases (Pinecone, Weaviate) - stick to EDP datastore ports (pgvector/sqlite-vss).",
        "Custom foundational LLM pre-training or weight fine-tuning.",
        "Unbudgeted global prompt broadcasts.",
    ],
    "ac": [
        "Context Router dynamically selects retrieval mode (Prompt, CAG, Vector RAG, Graph, Keyword) based on query classification.",
        "Knowledge Fabric registry enforces schema validation, authority tiers, and SHA-256 provenance on all knowledge chunks.",
        "Hybrid retrieval combines dense vector embeddings with BM25 lexical search and RRF ranking.",
        "CAG context cache achieves >=40% prompt token reduction on repeated pipeline executions with zero stale cache served.",
        "Prompt Compiler enforces hard per-stage token budgets with priority-driven truncation defense.",
        "Authority engine detects contradictions and enforces SSOT/ADR superiority over unverified or superseded claims.",
        "Evaluation harness verifies retrieval recall@5 >= 90% against golden query benchmarks.",
    ],
    "dod": [
        "Epic architecture and component interfaces approved at Gate 1.",
        "All child features delivered with 0 blockers / 0 majors.",
    ],
    "value": 5, "effort": 4, "risk": 2, "moscow": "Must",
    "references": [
        "docs/Product_Forge_RAG_CAG_Knowledge_Fabric_Integration.md",
        "docs/RAG-PROCESS-MEMORY.md",
        "docs/EDP-STORE-STATUS-AND-CONCURRENCY.md",
        "docs/Product_Forge_Enterprise_Performance_Security_DB_Storage_Roadmap.md",
    ],
}

ITEMS = [
    {
        "ext": f"{EXTERNAL}:context-knowledge-router",
        "title": "Context & Knowledge Router: query intent classification, retrieval mode selection, and budget routing",
        "problem": "Agents query knowledge monolithically or rely on full context dumps without understanding query intent or retrieval cost.",
        "goal": "Build the Context/Knowledge Router that analyzes incoming agent queries and dynamically routes between prompt context, CAG cache, vector RAG, keyword BM25, and knowledge graphs.",
        "in_scope": [
            "Intent classifier for factual, architectural, operational, and code-pattern queries.",
            "Dynamic mode selector: Prompt vs CAG vs Vector RAG vs Graph vs Keyword.",
            "Fallback degradation: fallback to lexical or working memory if vector/graph services are unreachable.",
            "Telemetry on query routing decisions and retrieval latencies.",
        ],
        "out_scope": ["Heavy ML classifiers requiring dedicated GPU inference."],
        "ac": [
            "AC-1: Router classifies query intent into factual, architectural, past_decision, procedural, or trace categories.",
            "AC-2: Routes to the optimal retrieval substrate with configurable routing policies per pipeline stage.",
            "AC-3: Automatically degrades to lexical search or working prompt memory if vector service is offline.",
            "AC-4: Routing latency overhead is under 5ms for local operations.",
        ],
        "dod": ["Unit and integration tests verify deterministic routing decisions."],
        "files": ["core/context_router.py", "go/pfrag/router.go", "go/pfrag/router_test.go"],
        "value": 4, "effort": 3, "risk": 2, "moscow": "Must", "deps": [],
        "references": ["docs/Product_Forge_RAG_CAG_Knowledge_Fabric_Integration.md#section-14"],
    },
    {
        "ext": f"{EXTERNAL}:knowledge-registry",
        "title": "Governed Knowledge Fabric & Registry: asset registration, schema validation, authority tiers, and SHA-256 provenance tracking",
        "problem": "Knowledge assets (ADRs, SSOT docs, code standards, glossaries) lack a formal registry, versioning, and tamper-evident provenance.",
        "goal": "Implement the Knowledge Fabric registry inside Product Forge to register, validate, version, and trace all authoritative knowledge assets.",
        "in_scope": [
            "Knowledge registry schema (asset_id, category, authority_tier, version, sha256, owner, valid_until).",
            "Validation gate rejecting unclassified, unversioned, or invalid knowledge chunks.",
            "Cryptographic provenance: every chunk links back to source file, heading anchor, and git commit SHA.",
        ],
        "out_scope": ["Third-party standalone OKF servers; keep logic natively integrated inside Product Forge."],
        "ac": [
            "AC-1: Registry tracks all core docs, ADRs, patterns, and guidelines with SHA-256 checksums.",
            "AC-2: Rejects registration of malformed or unversioned knowledge assets.",
            "AC-3: Injected context chunks include clickable provenance references and authority tier metadata.",
        ],
        "dod": ["Registry conformance tests pass with 100% metadata coverage across active docs."],
        "files": ["core/knowledge_registry.py", "go/pfrag/registry.go", "config/knowledge-registry.json"],
        "value": 4, "effort": 3, "risk": 1, "moscow": "Must", "deps": [],
        "references": ["docs/Product_Forge_RAG_CAG_Knowledge_Fabric_Integration.md#section-7", "docs/Product_Forge_RAG_CAG_Knowledge_Fabric_Integration.md#section-16"],
    },
    {
        "ext": f"{EXTERNAL}:hybrid-retrieval-engine",
        "title": "Pluggable Hybrid Retrieval Engine: Reciprocal Rank Fusion (RRF), BM25 keyword scoring, and semantic reranking over MemoryRepository",
        "problem": "Pure vector search suffers from semantic drift and poor keyword matching; pure lexical search fails on semantic paraphrasing.",
        "goal": "Implement hybrid retrieval combining dense vector embeddings (via datastore.MemoryRepository) with BM25 full-text search and Reciprocal Rank Fusion (RRF).",
        "in_scope": [
            "HybridSearchProvider interface querying both vector store and lexical indexes.",
            "Reciprocal Rank Fusion (RRF) algorithm merging candidate ranked lists.",
            "Semantic reranking stage filtering near-duplicate spans and noise.",
        ],
        "out_scope": ["Hardware-accelerated cross-encoders in local CLI mode."],
        "ac": [
            "AC-1: Executes vector and BM25 queries in parallel and fuses results via RRF.",
            "AC-2: Query equivalence and ranking stability verified across SQLite-vss and pgvector backends.",
            "AC-3: Filters out chunks below relevance threshold and deduplicates overlapping document spans.",
        ],
        "dod": ["Hybrid retrieval benchmarks demonstrate superior recall over vector-only and BM25-only baselines."],
        "files": ["core/hybrid_search.py", "go/pfrag/hybrid.go", "go/pfrag/hybrid_test.go"],
        "value": 4, "effort": 3, "risk": 2, "moscow": "Must", "deps": ["context-knowledge-router", "knowledge-registry"],
        "references": ["docs/Product_Forge_RAG_CAG_Knowledge_Fabric_Integration.md#section-8", "docs/RAG-PROCESS-MEMORY.md#section-8"],
    },
    {
        "ext": f"{EXTERNAL}:cag-context-cache",
        "title": "CAG Context Cache: pre-computed static context caching, prefix KV-cache reuse, and deterministic invalidation hooks",
        "problem": "Static and slow-moving context (system prompts, tool specs, core platform rules) is redundantly serialized and parsed on every LLM call.",
        "goal": "Deliver Cache-Augmented Generation (CAG) with pre-computed prefix caching and deterministic invalidation hooks.",
        "in_scope": [
            "Prefix context cache generating deterministic keys from content hashes.",
            "Invalidation hooks bound to git commit SHAs, file updates, and config changes.",
            "Freshness validation preventing stale cache injection.",
        ],
        "out_scope": ["Caching dynamic per-run agent scratchpad state."],
        "ac": [
            "AC-1: Caches static system prompts and rule sets with deterministic SHA-256 keys.",
            "AC-2: Modifying an underlying source document or rule invalidates the cache immediately.",
            "AC-3: Reduces prompt token consumption by >=40% on repeated invocations.",
        ],
        "dod": ["Cache invalidation and freshness integration tests pass with zero stale hits."],
        "files": ["core/cag_cache.py", "go/pfrag/cache.go", "go/pfrag/cache_test.go"],
        "value": 4, "effort": 3, "risk": 2, "moscow": "Should", "deps": ["knowledge-registry"],
        "references": ["docs/Product_Forge_RAG_CAG_Knowledge_Fabric_Integration.md#section-10", "docs/Product_Forge_RAG_CAG_Knowledge_Fabric_Integration.md#section-11"],
    },
    {
        "ext": f"{EXTERNAL}:context-prompt-compiler",
        "title": "Context & Prompt Compiler: dynamic budget allocation, sliding token budgets, section prioritization, and truncation defense",
        "problem": "Ad-hoc string concatenation of prompts causes context window overflow, silent truncation of critical rules, and high token costs.",
        "goal": "Implement the Context and Prompt Compiler enforcing strict token budgets per agent and stage, with deterministic prioritization and truncation defense.",
        "in_scope": [
            "Token budget manager allocating budget across System, CAG Prefix, Memory/RAG, and Scratchpad.",
            "Priority-ranked context section assembler.",
            "Truncation defense strictly protecting non-negotiable rules and task objectives.",
        ],
        "out_scope": ["Arbitrary unbudgeted prompt expansion."],
        "ac": [
            "AC-1: Every prompt assembly runs under an explicit token budget ceiling.",
            "AC-2: Lower-priority historical context is truncated before core rules or task objectives are affected.",
            "AC-3: Produces audit metadata detailing token allocations per section.",
        ],
        "dod": ["Compiler tests prove context never exceeds configured token limits under high payload volume."],
        "files": ["core/prompt_compiler.py", "go/pfrag/compiler.go", "go/pfrag/compiler_test.go"],
        "value": 4, "effort": 3, "risk": 1, "moscow": "Must", "deps": ["context-knowledge-router"],
        "references": ["docs/Product_Forge_RAG_CAG_Knowledge_Fabric_Integration.md#section-12", "docs/Product_Forge_RAG_CAG_Knowledge_Fabric_Integration.md#section-17"],
    },
    {
        "ext": f"{EXTERNAL}:authority-conflict-resolution",
        "title": "Knowledge Authority & Conflict Resolution: hierarchy enforcement, contradiction detection, and fail-closed HIL escalation",
        "problem": "Conflicting rules or stale memory entries injected into prompts confuse the model, leading to silent drift and hallucination.",
        "goal": "Enforce strict authority ordering (SSOT > ADR > Decision > Learned) and fail-closed contradiction detection before context enters prompts.",
        "in_scope": [
            "Authority hierarchy evaluator.",
            "Contradiction detection between candidate chunks and active SSOT rules.",
            "Fail-closed escalation halting injection on unresolvable same-tier contradictions.",
        ],
        "out_scope": ["Silent automated resolution of contradictory high-level business requirements."],
        "ac": [
            "AC-1: Higher authority tier deterministically overrides lower authority claims.",
            "AC-2: Contradiction detection flags conflicting polarities between active knowledge entries.",
            "AC-3: Same-tier conflict halts and triggers human-in-the-loop (HIL) escalation.",
        ],
        "dod": ["Contradiction tests verify fail-closed escalation and proper authority override."],
        "files": ["core/authority_engine.py", "go/pfrag/authority.go", "go/pfrag/authority_test.go"],
        "value": 4, "effort": 3, "risk": 2, "moscow": "Must", "deps": ["knowledge-registry"],
        "references": ["docs/Product_Forge_RAG_CAG_Knowledge_Fabric_Integration.md#section-15", "docs/RAG-PROCESS-MEMORY.md#section-6"],
    },
    {
        "ext": f"{EXTERNAL}:retrieval-evaluation-harness",
        "title": "Retrieval & Context Evaluation: Precision@k, Recall@k, faithfulness scoring, ground-truth benchmark suite, and latency observability",
        "problem": "No quantitative evaluation exists to measure if retrieved context is accurate, relevant, or hallucination-inducing.",
        "goal": "Build an automated evaluation harness measuring retrieval precision, recall, faithfulness, and latency across backends.",
        "in_scope": [
            "Evaluation harness computing Precision@k, Recall@k, MRR, and NDCG.",
            "Golden query-document benchmark dataset for Product Forge.",
            "Latency and context efficiency metrics exported to test reports.",
        ],
        "out_scope": ["Manual ad-hoc human-only grading."],
        "ac": [
            "AC-1: Evaluator runs automated queries against golden benchmark dataset.",
            "AC-2: Verifies Recall@5 >= 90% and Precision@5 >= 80% on standard test suite.",
            "AC-3: Detects performance regressions and context bloat in CI runs.",
        ],
        "dod": ["Evaluation harness integrated into CI with automated pass/fail assertions."],
        "files": ["engineering/benchmarks/rag/eval_harness.py", "engineering/benchmarks/rag/golden_queries.json"],
        "value": 3, "effort": 3, "risk": 1, "moscow": "Should", "deps": ["hybrid-retrieval-engine", "context-prompt-compiler"],
        "references": ["docs/Product_Forge_RAG_CAG_Knowledge_Fabric_Integration.md#section-24"],
    },
]

WAVES = {
    "context-knowledge-router": 1,
    "knowledge-registry": 1,
    "hybrid-retrieval-engine": 2,
    "cag-context-cache": 2,
    "context-prompt-compiler": 3,
    "authority-conflict-resolution": 3,
    "retrieval-evaluation-harness": 4,
}

API_IMPACT = {
    "epic": "coordination epic; delivered through internal Go/Python retrieval and prompt surfaces",
    "context-knowledge-router": "internal Go/Python query routing; no public HTTP route required",
    "knowledge-registry": "internal schema and asset validation; registry query API",
    "hybrid-retrieval-engine": "extends datastore.MemoryRepository / SearchProvider port",
    "cag-context-cache": "internal prefix cache provider; no external network API",
    "context-prompt-compiler": "internal agent runner prompt compilation API",
    "authority-conflict-resolution": "internal governance validator; gate evaluation check",
    "retrieval-evaluation-harness": "CI/benchmark CLI harness; no runtime HTTP API",
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
