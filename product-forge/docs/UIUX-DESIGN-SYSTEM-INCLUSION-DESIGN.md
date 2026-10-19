# UI/UX & Design-System Inclusion — Design (framework-agnostic)

**Status:** design / Gate 1 (no implementation yet)
**Scope:** `product_forge`
**Sources combined:** (a) the `UIUX/` research corpus (`REPORT.md` + 18 design-system teardowns + 10 fundamentals + patterns + 7 samples), and (b) the OpenCode UI/UX skills under `.opencode/skills/`.
**Precedent followed:** `docs/AGNOSTIC-CARDS-DESIGN.md` (BI-0201) and `docs/VENDORED-TOOLS.md` (BI-0202) — *neutral-first, `.opencode/` demoted to legacy fallback, Product Forge owns its truth.*
**Language rule:** `config/language-rule.json` + `core/change_policy.py` — **new shipped logic lands in Go** (`go/pfcore/`, op invoked via `core/go_host.py`); edits to existing shipped Python are allowed; tooling (`scripts/`, `docs/`, `config/`, `pipeline/`, `templates/`, `test-framework/`) may stay Python.

---

## 1. Goal

Make Product Forge able to **dynamically pick a UI/UX design direction from a project idea**, then generate **end-to-end UI components** for it — using a **PF-owned, framework-agnostic** knowledge base and skills, with `.opencode` as a pure adapter (never a dependency).

Two knowledge sources are merged:

| Source | Nature | Becomes |
|---|---|---|
| `UIUX/` corpus | knowledge — *what* good looks like (18 systems, ingredients, patterns, runnable samples) | PF **guidelines** + **machine catalog** + **reference baselines** |
| `.opencode/skills/*` | capability — *how* to apply judgement (procedures) | PF-owned **skills** + registry entries + agent bindings |

**UIUX = knowledge ("what"); skills = capability ("how"). Both must be owned by PF.**

---

## 2. Target architecture (levels)

```
L6  GATES      design_critic · a11y-audit (axe/pa11y/lighthouse, fail-closed) · visual_qa
L5  AGENTS     design · product-design-spec · design_critic · ux-ia · implement-ui · visual_qa (+skills)
L4  SELECTION  design_system_catalog + docs/design-direction.md + HIL "suggest" gate   ← dynamic pick
L3  SKILLS     pipeline/skills/<id>/SKILL.md (PF-owned) + skill resolver + registries
L2  MACHINE    config/design-systems.json + design_tokens (3-tier OKLCH, light+dark)
L1  KNOWLEDGE  docs/guidelines/ui-ux/* + docs/guidelines/design-systems/*  (auto-injected into prompts)
L0  REFERENCE  docs/reference/uiux-samples/* (runnable baselines) + golden fixtures
```

---

## 3. Placement — from → to

### 3a. OpenCode skills → PF-owned skills
Neutral home: **`product-forge/pipeline/skills/<id>/SKILL.md`** (existing `pipeline/skills/` dir; no new top-level dir — AGENTS.md #5).

| From `.opencode/skills/…` | To `product-forge/pipeline/skills/…` |
|---|---|
| `design-taste/SKILL.md` | `design-taste/SKILL.md` |
| `frontend-design/SKILL.md` | `frontend-design/SKILL.md` |
| `google-stitch-uiux/SKILL.md` | `google-stitch-uiux/SKILL.md` |
| `design-dna-extractor/SKILL.md` | `design-dna-extractor/SKILL.md` |
| `visual-regression-aesthetics/SKILL.md` | `visual-regression-aesthetics/SKILL.md` |
| `heuristic-evaluation/SKILL.md` | `heuristic-evaluation/SKILL.md` |
| `product-designer/SKILL.md` | `product-designer/SKILL.md` |
| `skill-router/SKILL.md` | `skill-router/SKILL.md` |
| `.opencode/skills/*` (remainder) | **legacy fallback** — not read by default |

Copy the **body + frontmatter + any `LICENSE.txt`/attribution verbatim** (§8 licensing).

### 3b. UIUX corpus → PF guidelines / reference
| From `Exploring/UIUX/…` | To `product-forge/…` |
|---|---|
| `REPORT.md` §2, §8 | `docs/guidelines/ui-ux/design-principles.md`, `docs/guidelines/ui-ux/anti-patterns.md` |
| `REPORT.md` §4 + `docs/uix-fundamentals/*` | `docs/guidelines/ui-ux/foundations.md` (+ per-ingredient files) |
| `docs/uix-fundamentals/components-inventory.md` | `docs/guidelines/ui-ux/components.md` |
| `docs/uix-patterns/ux-patterns.md` | `docs/guidelines/ui-ux/patterns.md` |
| `REPORT.md` §3 | `docs/guidelines/ui-ux/design-selection.md` |
| `REPORT.md` §5 | `docs/guidelines/ui-ux/implementation-stack.md` |
| `REPORT.md` §7 | `docs/guidelines/ui-ux/trends-2026.md` |
| `REPORT.md` §4.4 | **upgrade** `docs/guidelines/ui-ux/accessibility.md` → WCAG 2.2 |
| `docs/design-systems/*.md` (18) | `docs/guidelines/design-systems/<system>.md` |
| `samples/**` (7 + comparison) | `docs/reference/uiux-samples/**` |

### 3c. Machine-readable layer
| New file | Owner (single writer) |
|---|---|
| `config/design-systems.json` | design-system catalog engine (Go op) |
| `docs/guidelines/design-systems/README.md` | generated index |

---

## 4. Code to add / change (Go-first)

**Go (new logic — always language-rule compliant) under `go/pfcore/`, invoked via `core/go_host.py`:**
| New Go file | Concern | PF op |
|---|---|---|
| `go/pfcore/skill_registry.go` | resolve skill bodies neutral-first (`pipeline/skills/` → legacy `.opencode/skills/` only behind `ALLOW_OPENCODE_LEGACY=1`); list skill descriptions for the skill-router | `skills.resolve`, `skills.list`, `skills.describe` |
| `go/pfcore/design_system.go` | load `config/design-systems.json`; `select_for_product(product_type, domain, requirements) -> DesignDirection` (implements REPORT §3 tree); rank candidates | `design.select`, `design.catalog` |
| `go/pfcore/design_tokens.go` | 3-tier token build (global→alias→component), OKLCH ramps, light+dark, seeded by a direction | `design.tokens` |
| `go/pfcore/a11y_audit.go` | axe/pa11y/lighthouse orchestration + WCAG 2.2 AA verdict (fail-closed) | `a11y.audit` |

**Python (edits to existing shipped modules — allowed):**
| Module | Edit |
|---|---|
| `core/go_host.py` | add wrappers `skills_resolve/list/describe`, `design_select/catalog`, `design_tokens`, `a11y_audit` |
| `core/skills_registry.py` | neutral resolution + register the 8 skills as catalog entries |
| `core/knowledge_registry.py` | accept `kind:"skill"` entries whose `path` is a neutral skill body; expose to `resolve_layers` |
| `core/design_tokens.py` | consume the Go token engine (keep it the single writer of `tokens.json`) |
| `core/product_design_spec.py` | consume `DesignDirection` |
| `core/design_critic.py` | checks from `anti-patterns.md` + non-negotiables + catalog conformance |
| `core/visual_qa.py` | execute `visual-regression-aesthetics`; compare vs direction + sample baselines |
| `core/orchestrator/agent_runner.py` | inject a `SKILLS:` block (`_load_knowledge_for_agent` ~`:1679`; block ~`:1419`) |
| `core/knowledge_compliance_checker.py` | `GuidelineContentLoader` loads skill bodies from `pipeline/skills/` (`:456`) |

**Tooling/config (Python/JSON allowed):**
| Artifact | Action |
|---|---|
| `config/knowledge-registry.json` | register the 8 skills (`kind:"skill"`, `path`, `layers`, `agents`) |
| `config/agent-capabilities.json` | bind skills→agents |
| `config/store-registry.json` | register `config/design-systems.json` (`kind:config`); allow-globs for `docs/reference/uiux-samples/**`, `pipeline/skills/**` |
| `agents/*.agent.json` | add skills + `knowledge_layers:[ui-ux, design-systems]` + `allowed_inputs:[design_direction]` |
| `pipeline-definition.json` | add stage **1-0 "Design Direction"** (HIL suggest gate) + wire **a11y-audit** stage |
| `test-framework/templates/accessibility/` | create (missing today) |

---

## 5. Dynamic selection — pick a design from the idea, suggest it, build E2E components

```
0a/0e classification ─► product_type + domain + requirements
        ▼
design.select (Go)  uses docs/guidelines/ui-ux/design-selection.md tree + config/design-systems.json
        │  returns 2–3 ranked DesignDirection candidates:
        │   { mentor_system, style_family, stack, palette(OKLCH), radius/type/motion dials,
        │     component_set[], accessibility_target }
        ▼
[STAGE 1-0  HIL "suggest" GATE] ─► operator sees candidates + rationale → confirms/picks
        ▼
docs/design-direction.md  +  design-spec.json   (recorded decision, referenced by item_id)
        ▼
1a product-design-spec ─► screens/flows/states + E2E component build order
1c ux-ia/design.tokens ─► 3-tier OKLCH tokens, light+dark, from the chosen system
4x implement-ui         ─► builds the full component set (SKILLS: block injected)
4x-vqa + a11y.audit     ─► visual + WCAG 2.2 AA fail-closed gate
```

**E2E components** come from `docs/guidelines/ui-ux/components.md` + the chosen `design-systems/<system>.md`: the full build order (Button → Input → Form → Nav → Card → Overlay → Feedback → Table → Command palette) with the universal state matrix — rendered as the static prototype in Stage 4-0 and validated by L6 gates.

---

## 6. Backlog breakdown (epic + children, dependencies, waves)

**Epic:** *Design System & UI/UX Knowledge (framework-agnostic)*.

| ID | Child | Depends on (REQUIRES) | Wave | Language |
|---|---|---|---|---|
| DSI-1 | Framework-agnostic skills home + resolver | — | 1 | new **Go** + edits; `pipeline/skills/**` tooling |
| DSI-2 | UIUX knowledge ingestion (guidelines, design-systems, samples) | — | 1 | tooling/docs |
| DSI-3 | Design-system catalog store + selection engine | DSI-2 | 2 | new **Go** + `config/design-systems.json` |
| DSI-4 | Design-token engine upgrade (3-tier OKLCH, light+dark) | DSI-3 | 3 | new **Go** + edit `core/design_tokens.py` |
| DSI-5 | Dynamic design-direction stage + HIL suggest gate | DSI-3, DSI-4 | 4 | edit `pipeline-definition.json` + Go |
| DSI-6 | Skill/guideline prompt injection (`SKILLS:` block) | DSI-1 | 2 | new **Go** + edit `agent_runner.py` |
| DSI-7 | Agent skill & knowledge-layer bindings | DSI-1, DSI-6 | 3 | tooling/config |
| DSI-8 | Accessibility engine + fail-closed gate + templates | DSI-2 | 2 | new **Go** + stage |
| DSI-9 | design_critic / visual_qa integration | DSI-3, DSI-6 | 3 | edits |

**Execution order (waves):** `1 {DSI-1, DSI-2}` → `2 {DSI-3, DSI-6, DSI-8}` → `3 {DSI-4, DSI-7, DSI-9}` → `4 {DSI-5}`.

Each item: dedup-checked (`core.backlog --similar`), feature branch off `develop`, Go for new logic, evidence linked, merge immediately after green.

---

## 7. Gates / Definition of Done

`python -m compileall -q core scripts dashboard` · `python scripts/dev/wired_audit.py` (0 unwired) ·
`python scripts/dev/language_rule_check.py` (Go used for new logic) · `precheck` PASS ·
store registered in `config/store-registry.json` · skills registered · a11y + visual gates green · docs updated.
**No runtime module defaults to reading `.opencode`.**

---

## 8. Licensing (must be preserved on copy)

Several skills carry licenses/attribution — **copy the frontmatter + `LICENSE.txt` verbatim**, keep attribution lines:
- `design-taste` — MIT (`Leon Lee`, taste-skill v2)
- `design-dna-extractor` — MIT (`senlindesign`)
- `frontend-design` — **Anthropic Skills License (see `LICENSE.txt`)** — include the license file
- `visual-regression-aesthetics` — MIT
- `product-designer` — MIT + Commons Clause
- `e2e-testing-claude-code`, `playwright-pro` — MIT / MIT + Commons Clause
- `google-stitch-uiux`, `heuristic-evaluation`, `skill-router` — no license declared (record provenance: "ported to Product Forge")
- `architect` — Apache-2.0

Commit a `NOTICE`/`pipeline/skills/<id>/LICENSE.txt` where one exists; keep `source` + `attribution` in frontmatter.

---

## 9. Open decisions

1. Neutral skills home — **`pipeline/skills/<id>/SKILL.md`** (recommended, chosen) vs `docs/skills/…`.
2. `.opencode/skills/` → **legacy fallback** (recommended) vs generated mirror.
3. UIUX corpus — **stays in `Exploring/` as research; distilled copy lands in PF** (recommended).
4. Samples → **`docs/reference/uiux-samples/`** (recommended).
