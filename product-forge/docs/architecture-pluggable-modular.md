# Pluggable / Modular Architecture — Principles, Industry Benchmark, Differentiators

**Status:** design / principle. Backlog: epic **BI-0195** (pluggable core + standards adoption).
**Companion:** docs/multimodal_orchestration.md, docs/multimodal_selection_dynamic.md.

---

## 1. Principle — pluggable first, modular by default
Everything variable is a **plugin behind a port**; the core orchestrator depends only on the port.

- **Ports & adapters:** providers, model adapters, generators, tools, validators, agents, stages.
- **Registries over code:** new capability = a registry entry + a small adapter, not a core edit
  (mirrors what we already do: knowledge-registry, store-registry, capability packs).
- **Single-writer stores + derived files** (existing repo rule) → replaceable, testable, reproducible.
- **Config/env/user-driven:** per-project overrides (`products/<p>/...`) + `config/`; nothing hard-coded.
- **Scalability:** horizontal per project/run; **adaptability:** packs/knowledge/tools switch on by need.

### Plugin kinds (what must be pluggable)
`provider (direct|aggregator|self-host) · model-adapter (kind) · generator · tool · agent · stage ·
knowledge layer · skill · validator · capability pack · router policy`.

## 2. Industry & standards benchmark (2026)
**Open standards**
- **MCP — Model Context Protocol:** agent ↔ tools/data (tool discovery + call). *De-facto standard.*
- **A2A — Agent2Agent:** agent ↔ agent interop across frameworks/vendors. Complementary to MCP.
- **AG-UI:** agent ↔ user/frontend; typed **event stream** (run/tool/message lifecycle).
- **ACP:** agent ↔ IDE/editors (dev tools).
- **OpenTelemetry GenAI:** agent observability — spans for reasoning, tool calls, MCP calls,
  **multimodal prompts/responses** (Cloud Trace/BigQuery).
- **Durable execution (Temporal-style):** workflow durability, resume, long-running state.

**Frameworks / platforms**
- **LangGraph + LangSmith** (agent orchestration + observability/evals), **LangChain**, **CrewAI**,
  **AutoGen**, **Google ADK**, **Temporal** (generic durable workflows).
- **Media/creative:** ComfyUI (node graph), fal.ai / Replicate (model hosting), Runway (studio+API).
- **Product/software-agent builders:** Devin, Factory, Lovable, v0, Bolt, Replit Agent, n8n/Zapier Agents.

## 3. Table-stakes (parity we must have)
1. **Tool protocol (MCP)** — expose our tools; consume external MCP servers.
2. **Agent interop (A2A)** — call/be-called by other agent systems.
3. **Frontend event stream (AG-UI)** — the dashboard consumes a typed event stream (we have events; align).
4. **Durable execution + resume** — we have checkpoints/journal; align to the pattern explicitly.
5. **HITL** — we have it (BI-0093 gates).
6. **Memory (short + long term)** — we have project memory; make it first-class.
7. **Observability (OTel GenAI)** — spans for reasoning/tool/model calls incl. **media**.
8. **Evals + cost/token + latency per run/agent** — we have telemetry; standardize + extend to media units.
9. **Registries** (tools/agents/models) + **agent identity**.

## 4. What we ALREADY have (maps to standards)
| Standard capability | Our analogue |
|---|---|
| HITL | approval gates (BI-0093) |
| Durable/resume | checkpoints + journal + run-scope |
| Observability | telemetry/cost + events + logs/index |
| Memory | project memory |
| Registries | store-registry, knowledge-registry, model catalog, agent cards |
| Tools | core/tool_policy + tool loop |
| Governance | **wired_audit + pr_gate + frozen files + item_id traceability** |
| Quality | per-agent compliance (rule+knowledge+code-gate) + verification |

## 5. Differentiators — what we have (or should) that others don't
1. **End-to-end PRODUCT pipeline** (idea→discovery→design→architect→implement→validate→deploy), not a
   generic agent toolkit. Frameworks give primitives; we ship a governed product factory.
2. **Audit-first governance**: single-writer stores + `wired_audit` + PR gate + **frozen legacy guard** +
   `item_id` traceability. Rare outside enterprise; most frameworks have none.
3. **Capability packs auto-selected from the idea** → the harness adapts to env/user needs without config.
4. **Cost-aware, modality-pluggable routing** with **per-unit media costing** (free + paid mix) chosen
   *during project creation / tier assignment*.
5. **Knowledge/skills SSOT per agent** (+ role-driven compliance) — domain/business skills, not generic.
6. **Evidence/verification-first close-loop** (verify → auto-close backlog, reports attached).
7. **Reproducible artifacts + derived-notice discipline** (derived files generated, never hand-edited).

## 6. Gaps to close (adopt standards, keep differentiators)
- Adopt **MCP** (expose/consume tools) and **A2A** (agent interop) — interop without losing the harness.
- Align the dashboard stream to **AG-UI**; instrument with **OTel GenAI** (incl. media spans).
- Formalize the **plugin/registry framework** (ports+adapters) so new kinds/packs/tools need no core edits.
- Extend telemetry + costing to **per-unit media** (feeds BI-0194).

## 7. Mapping to code (how "pluggable" is realized)
- **Registries:** `config/store-registry.json`, `config/knowledge-registry.json`, model catalog,
  `config/capability-packs.json` (new), provider/adapter registry (new, BI-0193).
- **Ports:** tool loop (`tool_policy`), provider adapter contract (BI-0193), agent spec, stage def.
- **Packs:** capability packs (BI-0189) gate agents/tools/models per project.
- **Policy:** model-strategy gate (BI-0192) selects kind/provider/tier with cost (BI-0194).
