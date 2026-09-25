---
name: skill-router
description: Meta-skill for handling multi-source skill sets. When multiple skills cover overlapping or adjacent domains (e.g. UI/UX, security, testing), the agent must enumerate ALL relevant skills, load their summaries, and apply the UNION of capabilities — never pick just one. Read this skill whenever more than one skill in the agent's available set has a description matching the current task.
---

# Skill Router — Multi-Source Inclusion Protocol

## Problem

Product Forge skills are sourced from multiple ecosystems (Anthropic, community, our own). When two or more skills cover the same domain (UI/UX, security, testing, audio, etc.), the agent risks:

- **Picking one** based on star count or recency and ignoring others
- **Losing unique capabilities** from the skill it didn't pick
- **Producing incomplete output** that misses patterns from non-selected skills

## Rule: enumerate then union

When **two or more available skills match the current task**, the agent MUST:

1. **List** every skill whose `description:` field matches the task keywords
2. **Load the description (only)** of each — not the full body (to save tokens)
3. **Compare** their capabilities — note which is unique vs overlapping
4. **Apply the union** — use the right skill for each sub-task
5. **Cite** which skill informed each decision in the output

## When to apply

Trigger this skill when ANY of these is true:
- More than one skill has a description matching the task
- A sub-task uses capability X and another uses capability Y, where each skill covers one
- The user explicitly says "use the best of" or "consider all relevant skills"
- The orchestrator invokes a chain like `[skill-a, skill-b, skill-c]` for a stage

## When NOT to apply

Skip if exactly one skill matches. Don't add overhead for the simple case.

## Example: UI/UX task

Available skills that match "build a UI":
- `design-taste` — anti-slop typography + layout discipline + dials (variance/motion/density)
- `design-dna-extractor` — extract aesthetic from a reference site via Playwright
- `frontend-design` — Anthropic's canonical design-lead instructions
- `product-designer` — broad UX process (research, journey maps, design systems)
- `heuristic-evaluation` — audit against Nielsen/Shneiderman

**Wrong:** Pick `design-taste` (highest stars) and ship. Misses the DNA-extraction capability for "make it look like Linear".

**Right:**
1. Detect "build UI" → 5 skills match
2. Read description of each
3. Sub-task split:
   - User said "looks like Linear" → use `design-dna-extractor` first to extract Linear's tokens + trade-offs
   - Then apply `design-taste` with those tokens as constraints
   - Then `frontend-design` for hero-as-thesis and writing rules
   - `product-designer` for journey map + wireframes (if user wants process artifacts)
   - `heuristic-evaluation` at the end as audit pass
4. Output cites which skill informed which decision

## Workflow

```
TASK
  ↓
[Enumerate matching skills by keyword]
  ↓
{skill_a, skill_b, skill_c, ...}
  ↓
[Load only the description: field of each — DO NOT load full body unless needed]
  ↓
[Diff capabilities — what's unique, what's overlapping]
  ↓
[Build a skill-routing plan: which skill for which sub-task]
  ↓
[Execute sub-tasks in order, calling each skill's full body when its sub-task is reached]
  ↓
[Cite skill attribution in final output]
```

## Implementation rules

### 1. Don't auto-load all skill bodies
Loading 10 full skill files into context wastes tokens. Load only the description fields first; load the body of a specific skill when its sub-task is reached.

### 2. Don't pick one and ignore others
The "best skill" framing is wrong. The right framing is "what's the right skill for THIS sub-task?"

### 3. Disambiguate by capability, not by metadata
When two skills both mention "typography", look at HOW they cover it. If they cover different aspects, both are needed.

### 4. Attribute in output
Every output that uses skill knowledge should cite which skill informed which decision. Example format:
```
Skills applied:
- design-dna-extractor: extracted Linear.app's tokens (see .taste/linear.json)
- design-taste: applied variance=6, motion=4, density=5 dials
- frontend-design: hero-as-thesis rule for the landing hero
```

### 5. Skill conflicts
If two skills give conflicting advice (e.g. taste-skill says use serif, frontend-design says use sans), apply this resolution order:
1. **User brief** — explicit user instructions always win
2. **Concrete context** — if a reference site has been extracted, that wins
3. **Most specific skill** — a skill that targets your exact stack (e.g. "React + Tailwind") wins over a general one
4. **Most authoritative skill** — Anthropic's canonical > community

Document the conflict and your resolution in the output.

## Token budget protocol

The multi-source rule MUST respect the agent's context window. Loading every skill body would blow context and degrade quality.

### Budget tiers

| Agent context budget | Max skill bodies loaded | Strategy |
|---|---|---|
| **Tight** (<8K tokens free) | 1 | Pick the single best skill. Don't union. |
| **Normal** (8-32K free) | 2-3 | Load description for all matching, body for top 2-3 |
| **Loose** (>32K free) | 4-5 | Full union, but reference, don't quote at length |
| **Plenty** (>64K free) | All | Full union, can quote at length |

### Lazy loading Pattern

```
For each sub-task:
  1. Check budget tier
  2. If tight: pick one skill body, read it once, complete sub-task, move on
  3. If normal: pick top 2-3 skill bodies by description match, read them, complete
  4. If loose/plenty: read all matching bodies, complete with full union
  5. NEVER re-read a skill body in the same turn (cache in mind, not context)
```

### Don't paste skill content into output

When a skill informs a decision, **cite** it (e.g. "per design-taste skill, banned pattern #1: cream + serif + terracotta") but don't reproduce the skill body. The audit trail in `.opencode/state/skill-usage.json` records what was used.

### Compression rules for output

- Reference skill by name, not by quoting it
- Summarize 20-item lists as bullets, don't enumerate
- Use diff format when comparing skill outputs ("X says Y, Z says W, pick X because...")
- Tokenize screenshots: don't paste base64; reference file path

### Example: tight-budget UI task

Available skills: design-taste, design-dna-extractor, frontend-design, product-designer, heuristic-evaluation.

Tight budget → pick ONE. Decision tree:
- User gave reference URL? -> design-dna-extractor
- Greenfield, "looks polished/premium"? -> design-taste
- Auditing? -> heuristic-evaluation

One skill loaded, complete the task, move on. No union needed.

### Example: loose-budget UI task

Same skills, loose budget.

```
Sub-task 1: pick reference aesthetic -> load design-dna-extractor body
Sub-task 2: apply taste rules -> load design-taste body
Sub-task 3: apply Anthropic canonical rules -> load frontend-design body
Sub-task 4: audit result -> load heuristic-evaluation body
```

Four skill bodies loaded across sub-tasks, but only one at a time. Net context cost ~ max(single body) = 5-15K tokens per sub-task. Cumulatively lower than loading all at once.

## Pre-computed skill sets

These are the known overlapping sets in Product Forge. Add to this list as new overlaps emerge.

### UI/UX
- `design-taste` — anti-slop typography, layout dials
- `design-dna-extractor` — Playwright-based reverse-engineering of reference sites
- `frontend-design` — Anthropic's canonical design-lead principles
- `product-designer` — broad UX process + journey maps + design systems
- `heuristic-evaluation` — Nielsen/Shneiderman audit pass
- **Routing:** For "build UI like X" → DNA-extract → taste apply → frontend-design rules. For "audit this UI" → heuristic-eval. For "user research / wireframes" → product-designer.

### Testing
- `e2e-testing-claude-code` — Playwright/Cypress flows, POM, fixtures
- `playwright-pro` — Playwright-specific deep dive (locators, flake, visual regression)
- `webapp-testing` (if installed) — Anthropic's minimal scaffold
- `tdd` — RED-GREEN-REFACTOR cycle, vertical slicing
- `testing-strategy` — overall testing strategy + coverage rules
- **Routing:** For "write e2e tests" → playwright-pro OR e2e-testing-claude-code (pick by stack). For "what to test + strategy" → testing-strategy. For "TDD workflow" → tdd.

### Security
- `security-analysis` — multi-phase security analysis
- `threat-modeling` — STRIDE
- `compliance-check` — regulatory compliance
- **Routing:** For "find vulns" → security-analysis. For "model threats" → threat-modeling. For "GDPR/SOC2" → compliance-check. Often chain all three.

### Audio / Voice
- `audio` — voice capabilities via VoiceStudio
- **Routing:** Standalone for now; revisit if multiple voice skills added.

### Media generation
- `image` — generate/edit images via ComfyUI
- `video` — generate videos via AnimateDiff
- `slides` — generate presentation decks via bolt-slides
- **Routing:** Distinct domains; no overlap.

## When this skill is itself loaded

If the agent sees this skill-router skill in its available set, it MUST apply the multi-source protocol above to its own planning — even if no other skill has yet asked it to. This is a self-applying rule.

## Audit trail

For every project that used multiple skills, generate `.opencode/state/skill-usage.json`:

```json
{
  "stage": "stage-4-implementation",
  "agent": "design",
  "skills_considered": ["design-taste", "design-dna-extractor", "frontend-design"],
  "skills_applied": ["design-dna-extractor", "design-taste"],
  "routing_decision": "Used DNA-extractor to learn Linear's aesthetic, then taste-skill to apply variance=6 dial; skipped frontend-design because user requested minimalist (overlaps with taste-skill's minimalist variant).",
  "output_attribution": "see .taste/linear.json + taste-skill dials in docs/design-decisions.md"
}
```

This makes skill selection auditable — important when an output is questioned.