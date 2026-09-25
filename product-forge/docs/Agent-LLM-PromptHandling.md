# Agent LLM Prompt & Response Handling — Analysis and Recommendations

> Date: 2026-08-24
> Source: Gemini feedback session + GitHub research
> Context: Multi-agent pipeline with 8 agents running different LLMs (Qwen 3.7 Max, Qwen 3.7 Plus, MiniMax M3, DeepSeek V4 Flash, Kimi 2.7 Code, MiMo v2.5)

---

## 1. Feedback Summary (Gemini Session)

### Core Problems Identified

| # | Problem | Description | Impact |
|---|---|---|---|
| 1 | **Prompt mismatch** | Prompts that work on large models (Qwen 3.7 Max) confuse smaller models. Each LLM interprets natural language differently. | Agents fail silently or produce wrong output |
| 2 | **Chunking breaks formatting** | Character-count chunking splits MD headers mid-section and JSON brackets `{}`, corrupting structure. | LLMs receive broken data, panic, output garbage |
| 3 | **Output format inconsistency** | Agent A outputs prose, Agent B expects JSON. No enforced contract between stages. | Pipeline crashes at handoff |
| 4 | **Token bloat** | Passing full files + conversation history + instructions to every agent multiplies prompt size exponentially. | "Prompt too large" errors, especially on 256K models |
| 5 | **Orchestrator fragility** | When one agent fails, the whole pipeline breaks. No automatic retry or fallback. | Manual intervention required |

### Models in Use

| Model | Context Window | Best Role | Weakness |
|---|---|---|---|
| Qwen 3.7 Max | Ultra-large | Orchestrator / Director | Wasted on small tasks |
| MiniMax M3 | 1M tokens | Deep analysis, long-doc processing | Overkill for simple extraction |
| Qwen 3.7 Plus | Large | Data processing, structured tasks | Breaks on malformed chunks |
| DeepSeek V4 Flash | 1M tokens | Fast processing, terminal tasks | Sensitive to formatting |
| Kimi 2.7 Code | 256K | Code generation, file writing | Needs parent header context |
| MiMo v2.5 | 1M tokens | Coding, iterative fixes | Needs clean input |

### File Types

All `.md` and `.json` files, approximately ~200KB each (~40,000-50,000 tokens). These fit easily within all model context windows — the issue is NOT context size, it's **inefficient data passing and broken formatting**.

---

## 2. GitHub Research Findings

### Top Solutions by Category

#### A. Structured Output Enforcement

| Project | Stars | Approach | Key Result |
|---|---|---|---|
| **BAML** | 8.2K | DSL with Schema-Aligned Parsing (SAP) | 100% parse success vs 87.1% for raw Pydantic |
| **Instructor** | — | Pydantic-based validation with auto-retry | Forces LLM to match schema, retries on failure |
| **LiteLLM structured outputs** | 54K | `supports_structured_outputs` flag per model | Routes to native or tool-based structured output |

**Key insight from BAML benchmark:** The 12.9% Pydantic failure rate was caused by "schema-echo" — smaller models mirror back the JSON Schema structure as output instead of the actual data. BAML's compact pseudo-schema (13 lines vs 62 lines) eliminates this.

#### B. Universal API / Multi-Model Routing

| Project | Stars | Approach |
|---|---|---|
| **LiteLLM** | 54K | Universal adapter normalizing 100+ providers to OpenAI format |
| **Orchester** | — | 80+ providers behind one adapter with cost control |
| **Sagent** | — | Hot-swapping providers mid-session, context compaction |

**LiteLLM key features:**
- Auto-routing by complexity (simple/medium/reasoning)
- Fallback chains (if Model A fails, try Model B, then Model C)
- Pre-flight token estimation to prevent context overflow
- `context_window_fallbacks` for automatic model switching on overflow

#### C. Context Management / Information Diet

| Project | Approach |
|---|---|
| **OMA (Open Multi-Agent)** | Workers get only specific data needed, not full files. Context compaction between steps. |
| **multiagentz** | Per-agent `max_context_chars` budget, pre-flight token estimation |
| **Tetora** | `!compact` command summarizes and carries forward session |

**Key pattern:** The "Ingestion → Extraction → Delegation" workflow:
1. Large model reads entire file (no chunking)
2. Extracts specific sections as self-contained snippets
3. Each snippet is sent to a specialized worker model

#### D. Document-Aware Chunking

| Approach | How It Works |
|---|---|
| **Markdown Header Splitter** | Split only at `#`, `##`, `###` boundaries |
| **Parent-Child Retrieval** | Tiny chunks for search → parent chunk for context |
| **JSON object iteration** | Parse JSON in Python, loop through objects (never character-split) |
| **Structural metadata** | Prefix each chunk with `[Context: # Section -> ## Subsection]` |

---

## 3. Recommendations for Current Pipeline

### Priority 1: Add Structured Output Schemas (Effort: Low, Impact: Critical)

**Problem:** Agent outputs are unvalidated text. No guarantee Agent B can parse Agent A's output.

**Solution:** Add explicit JSON output schema to every agent's prompt. Each agent must output a defined structure.

**Implementation:**
- Add `## OUTPUT FORMAT` section to every agent `.md` file
- Define exact JSON structure expected
- Orchestrator validates output before passing to next agent

### Priority 2: Add Context Compaction Between Stages (Effort: Medium, Impact: High)

**Problem:** Each agent receives full docs from all previous stages, causing token bloat.

**Solution:** After each stage completes, produce a compact summary (2-3 pages max) alongside the full artifact. Downstream agents receive:
- The compact summary (always)
- The full artifact (only if they need to reference specific details)

**Implementation:**
- Add to checkpoint protocol: "After completing your work, produce a 2-page summary of key decisions and output"
- Orchestrator passes summaries, not full docs, to the next agent
- Full docs remain available via file read if needed

### Priority 3: Enforce Information Diet (Effort: Low, Impact: High)

**Problem:** Every agent receives the same massive context bundle regardless of their role.

**Solution:** Each agent gets only what it needs:

| Agent | Needs | Does NOT Need |
|---|---|---|
| design | product-plan.md only | architecture.md, code |
| architect | requirements.md + design.md summary | full design.md color tokens |
| review | requirements.md + design.md + architecture.md | code details |
| implement | review.md (verdict) + architecture.md | full requirements |
| code-review | code + requirements.md | architecture.md |
| validate | code + requirements.md (acceptance criteria only) | full design docs |
| fix | reports/issues.md + relevant code | full architecture |

**Implementation:**
- Update each agent's prompt to list exactly which files/sections to read
- Orchestrator constructs targeted prompts with only relevant file references

### Priority 4: Structure-Based Chunking for File Reading (Effort: Low, Impact: Medium)

**Problem:** When agents read files, there's no guidance on how to handle large files.

**Solution:** Add file reading instructions to each agent:

**For Markdown files:**
- Read by header sections, not by character count
- Preserve parent headers when reading sub-sections
- Use offset/limit to read specific sections, not the whole file

**For JSON files:**
- Parse the full structure in memory (200KB is small for Python)
- Loop through objects, never character-split
- Extract only the relevant objects for the task

**Implementation:**
- Add `## FILE READING RULES` section to each agent's prompt
- Specify which sections of which files to read
- Instruct agents to use `Read` tool with offset/limit for large files

---

## 4. Implementation Checklist

- [ ] Priority 1: Add `## OUTPUT FORMAT` JSON schema to all 7 agent prompts
- [ ] Priority 2: Add context compaction instructions to checkpoint protocol
- [ ] Priority 3: Update each agent's `## INPUT` section with exact file list
- [ ] Priority 4: Add `## FILE READING RULES` to agent prompts
- [ ] Update orchestrator to validate agent outputs before stage handoff
- [ ] Test pipeline with all model tiers to verify reliability

---

## 5. References

- BAML benchmark: https://github.com/thisisvk45/baml-diligence-eval
- LiteLLM routing: https://docs.litellm.ai/docs/routing
- LiteLLM auto-routing: https://docs.litellm.ai/docs/proxy/auto_routing
- OMA framework: https://github.com/open-multi-agent/open-multi-agent
- multiagentz: https://github.com/ZlaylowZ/multiagentz
- Sagent: https://github.com/rekursiv-ai/sagent
- Orchester: https://github.com/lucasmailland/orchester
