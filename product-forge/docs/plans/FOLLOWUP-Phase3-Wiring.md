# FOLLOWUP: Phase 3 Advanced Features Wiring

> **Status**: DEFERRED — Infrastructure ready, not yet wired into agents
> **Date**: 2026-08-31
> **Priority**: LOW (only when complex multi-step reasoning is needed)

---

## Why Deferred

Phase 3 features are **built and tested** (in `core/phase3_advanced.py` and `core/loop_modes.py`), but they **don't auto-activate** like Phase 1-2 features do. They require explicit calls from agent code.

**Current state** (as of 2026-08-31):
- All Phase 3 modules exist and are importable
- They are not invoked by any agent
- They provide zero benefit until agent code is modified

**The agents are LLM-driven** (`.opencode/agent/*.md` files are prompts, not Python). Wiring means adding tool-calling instructions to each agent's prompt.

---

## Phase 3 Modules to Wire

### 1. `ToolResultCompressor` (core/phase3_advanced.py)

**What it does**: Compresses tool output from >1000 tokens to ~60-80% smaller while preserving meaning.

**Where to wire**:
- The orchestrator wraps every tool call
- Before returning tool output to the LLM, check size and compress if needed

**How to wire** (when ready):
```python
from core.phase3_advanced import ToolResultCompressor

compressor = ToolResultCompressor()

# In the tool-call wrapper
def wrapped_tool_call(tool_name, args):
    result = execute_tool(tool_name, args)
    is_log = tool_name.endswith("_log") or "log" in tool_name
    return compressor.compress(result, max_tokens=1000, is_log=is_log)
```

**Benefit**: 30-50% token reduction on tool outputs that are verbose (logs, file contents, API responses)

---

### 2. `AdaptiveReasoningController` (core/phase3_advanced.py)

**What it does**: Recommends reasoning depth (minimal/low/medium/high/maximum) based on task complexity. Adjusts max_tokens and iterations.

**Where to wire**:
- At the start of each agent invocation
- Agent reads the recommended depth and uses it to structure its reasoning

**How to wire**:
```python
from core.phase3_advanced import AdaptiveReasoningController

controller = AdaptiveReasoningController(products_dir)

# Before agent runs
depth = controller.assess_complexity(task, stage, prior_failures)
config = controller.get_config(depth)
# Tell agent: "Use max {config['max_tokens']} tokens and {config['iterations']} iterations"

# After agent completes
controller.record_outcome(depth, success=True, quality=0.85)
```

**Benefit**: Prevents over-thinking simple tasks (saves tokens) and under-thinking complex ones (improves quality)

---

### 3. `KnowledgeGraph` (core/phase3_advanced.py)

**What it does**: Links concepts across domains (e.g., "authentication" in backend links to "auth" in security links to "JWT" in API).

**Where to wire**:
- Augment the existing `KnowledgeRouter` (Phase 2.3) to use cross-domain links
- When loading knowledge for a task, also load related concepts from other domains

**How to wire**:
```python
from core.phase3_advanced import KnowledgeGraph

graph = KnowledgeGraph(products_dir)
# Pre-populate with concepts from guidelines
for resource in knowledge_router.resources.values():
    graph.add_node(resource.id, resource.domain, resource.title)
    # Auto-link related concepts
    for tag in resource.tags:
        graph.add_edge(resource.id, tag, "related", weight=0.5)

# When routing
related = graph.find_related(selected_resource, max_depth=2)
```

**Benefit**: Discovers relevant knowledge across domains that keyword matching misses

---

### 4. `SemanticCache` (core/phase3_advanced.py)

**What it does**: Caches results from semantically similar (not just identical) queries. Reuses answers for "How do I authenticate users?" and "What's the login flow?".

**Where to wire**:
- In the agent's main query loop, before calling the LLM
- Check if a similar query has been answered before

**How to wire**:
```python
from core.phase3_advanced import SemanticCache

cache = SemanticCache(products_dir)

# Before LLM call
cached = cache.get(query)
if cached:
    return cached

# After LLM call
result = llm_call(query)
cache.set(query, result, ttl_seconds=3600)
```

**Benefit**: 20-40% reduction in LLM calls for repetitive query patterns (e.g., "how do I..." questions)

---

### 5. `LoopController` (core/loop_modes.py)

**What it does**: Supports time-based and event-based execution loops for agent operations.

**Where to wire**:
- For long-running agents that need to poll/iterate (e.g., monitoring agents)
- For agents waiting on external events (e.g., waiting for CI to complete)

**How to wire**:
```python
from core.loop_modes import LoopController, LoopConfig

controller = LoopController(products_dir)

# Time-based: run for 1 hour, check every 60s
result = controller.execute_time_based(
    loop_id="monitor-deploy-123",
    action=check_deployment_status,
    duration_seconds=3600,
    interval=60,
)

# Event-based: run until "deploy-complete" event fires
result = controller.execute_event_based(
    loop_id="wait-for-deploy-123",
    action=check_deploy_health,
    event_name="deploy-complete",
    timeout_seconds=7200,
)

# When deploy finishes, in another agent:
controller.fire_event("deploy-complete", {"status": "success"})
```

**Benefit**: Enables long-running agents without blocking, supports event-driven workflows

---

## Decision: When to Wire

**Trigger conditions** (any of these means "wire Phase 3 now"):
1. MyWorld project has >50% token spend on tool outputs (compress)
2. Agents are over-thinking simple tasks (adaptive reasoning)
3. Knowledge Router misses relevant guidelines (knowledge graph)
4. Same questions asked >3x per day (semantic cache)
5. Need to monitor long-running operations (loop controller)

**Not needed if**:
- Token spend is already low (<$1/day)
- Agents complete in 1-2 iterations typically
- Knowledge Router is finding good matches
- No long-running operations

---

## Implementation Plan (When Triggered)

Estimated time: 4-6 hours total

| Step | Time | What |
|------|------|------|
| 1. Tool Compression | 1 hr | Wrap tool calls in orchestrator |
| 2. Adaptive Reasoning | 1 hr | Add depth check to agent prompts |
| 3. Knowledge Graph | 2 hr | Build graph from guidelines, augment router |
| 4. Semantic Cache | 1 hr | Add cache check to query layer |
| 5. Loop Controller | 1 hr | Add to long-running agents (deploy, monitor) |
| **Total** | **6 hrs** | |

---

## Files to Modify

When wiring:

1. **`core/orchestrator.py`** (or similar) - Add tool wrapper
2. **`.opencode/agent/*.md`** - Add adaptive reasoning instructions
3. **`core/knowledge_router.py`** - Integrate graph
4. **Agent query handler** - Add semantic cache
5. **Long-running agents** - Use loop controller

---

## Current Phase 3 Status

| Module | Built | Tested | Auto-Active | ROI |
|--------|-------|--------|-------------|-----|
| ToolResultCompressor | ✅ | ✅ | ❌ | High if many tool calls |
| AdaptiveReasoningController | ✅ | ✅ | ❌ | High if simple tasks over-thought |
| KnowledgeGraph | ✅ | ✅ | ❌ | Medium |
| SemanticCache | ✅ | ✅ | ❌ | High if repetitive queries |
| LoopController | ✅ | ✅ | ❌ | High for long-running ops |

**Bottom line**: Phase 3 is **ready when needed**, but the pipeline works fine without it. Don't wire until you see the trigger conditions above.
