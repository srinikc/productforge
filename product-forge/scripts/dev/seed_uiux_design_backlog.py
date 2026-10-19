"""Seed the Design System & UI/UX Inclusion epic + children (idempotent) via the backlog API ONLY.

Design: docs/UIUX-DESIGN-SYSTEM-INCLUSION-DESIGN.md
- Creates the epic, its child items, REQUIRES dependencies, and the epic execution order (waves).
- Each item gets authored context: brief/objective, Acceptance Criteria (testable) and Definition of Done.
- Grooming is performed by the backlog API on add (deterministic; run with PF_GROOMING_AI=0 to avoid live calls).
- Idempotent by ``external_id`` - re-running extends, never duplicates.

Run from the product-forge root:
  $env:PF_GROOMING_AI=0; python scripts/dev/seed_uiux_design_backlog.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core import backlog  # noqa: E402

S = "product_forge"
P = None
SRC = "design:UIUX-DESIGN-SYSTEM-INCLUSION-DESIGN.md"
EXTERNAL = "uiux-design-system-inclusion"

UNIVERSAL_DOD = [
    "Feature branch off develop (never commit to develop/main directly).",
    "Code review of the diff; findings fixed.",
    "Lint/static clean (scripts/dev/lint_check.py).",
    "language_rule_check PASS - new logic in Go (go/pfcore/*.go), edits to existing shipped Python only.",
    "precheck PASS (compileall, wired_audit, api/governance, engineering-flow, backlog-e2e, docs-fresh, secret-scan, pipeline tests).",
    "Evidence (artifact + test descriptors) linked on this item; intent_trace resolves.",
    "Merged to develop immediately after green; delivery provenance recorded (branch, merge_sha, pr).",
]


def body(problem, goal, in_scope, out_scope, ac, dod):
    def sec(title, lines):
        return f"## {title}\n" + "\n".join(f"- {x}" for x in lines) + "\n"
    return (
        f"## Problem / why\n{problem}\n\n"
        f"## Goal & value\n{goal}\n\n"
        + sec("In scope", in_scope) + "\n"
        + sec("Out of scope", out_scope) + "\n"
        + sec("Acceptance criteria", ac) + "\n"
        + sec("Definition of Done", dod) + "\n"
        + "## Verification / test plan\n" + "\n".join(f"- {x}" for x in ac) + "\n"
    )


EPIC = {
    "ext": f"{EXTERNAL}:epic",
    "title": "Design System & UI/UX Knowledge (framework-agnostic)",
    "problem": (
        "PF has UI/UX pipeline stages and a guideline loader, but only ~15 KB of dated a11y guidance behind "
        "them; the rich UIUX/ corpus and the OpenCode UI/UX skills are unused and/or harness-bound."
    ),
    "goal": (
        "Merge the UIUX/ corpus and the OpenCode skills into a PF-owned framework-agnostic knowledge+skills base, "
        "and let PF dynamically pick a design direction from a project idea and generate end-to-end UI components. "
        ".opencode becomes a pure adapter (BI-0201/BI-0202)."
    ),
    "in_scope": [
        "L1 guidelines, L2 catalog+tokens, L3 skills, L4 selection, L5 agent bindings, L6 a11y/visual gates.",
        "New logic in Go (go/pfcore) invoked via core/go_host.py.",
    ],
    "out_scope": ["Redesigning the pipeline itself", "Non-UI skills", "Generated-product code changes."],
    "ac": [
        "Given a project idea, PF suggests 2-3 ranked design directions at a HIL gate.",
        "Skills resolve neutral-first from pipeline/skills; no default .opencode read.",
        "Tokens are 3-tier OKLCH with light+dark, seeded by the chosen system.",
        "New logic lands in Go and passes scripts/dev/language_rule_check.py.",
    ],
    "dod": [
        "All child items complete and their gates green.",
        "A sample product end-to-end run produces a named design direction + tokens + passing a11y/visual gates.",
    ],
    "value": 5, "effort": 5, "risk": 3, "moscow": "Should",
}

ITEMS = [
    {
        "ext": f"{EXTERNAL}:skills-registry",
        "title": "Framework-agnostic skills home + resolver",
        "problem": "UI/UX skills live only under .opencode/skills/*/SKILL.md, coupling PF to the harness and leaving them unregistered.",
        "goal": "PF owns the skill bodies; .opencode is a legacy fallback only.",
        "in_scope": [
            "Copy the 8 UI/UX skills into pipeline/skills/<id>/SKILL.md (body+frontmatter+LICENSE verbatim).",
            "Neutral-first resolver (Go op skills.resolve/list/describe) via core/go_host.py.",
            "Register in config/knowledge-registry.json (kind:skill) and pipeline/skills-registry.json.",
        ],
        "out_scope": ["Migrating non-UI skills", "Deleting .opencode (kept as legacy fallback)."],
        "ac": [
            "Given a skill id, skills.resolve returns the neutral body from pipeline/skills/<id>/SKILL.md.",
            ".opencode/skills is read only when ALLOW_OPENCODE_LEGACY=1.",
            "Both registries contain the 8 skills; license/attribution preserved.",
        ],
        "dod": ["wired_audit green (no unwired file).", "skills.resolve covered by a unit test."],
        "files": ["go/pfcore/skill_registry.go", "core/go_host.py",
                  "config/knowledge-registry.json", "pipeline/skills-registry.json"],
        "value": 5, "effort": 3, "risk": 2, "moscow": "Should", "deps": [],
    },
    {
        "ext": f"{EXTERNAL}:knowledge-ingestion",
        "title": "UIUX knowledge ingestion (guidelines, design-systems, samples)",
        "problem": "docs/guidelines/ui-ux holds only a dated WCAG-2.1 accessibility.md; the UIUX/ corpus is unused.",
        "goal": "Distill UIUX/ into PF guidelines + reference baselines the existing loader already injects.",
        "in_scope": [
            "Add docs/guidelines/ui-ux/* (principles, anti-patterns, foundations, components, patterns, design-selection, stack, trends).",
            "Upgrade accessibility.md to WCAG 2.2 AA.",
            "Add docs/guidelines/design-systems/* (18) and docs/reference/uiux-samples/*; register allow-globs.",
        ],
        "out_scope": ["Authoring NEW design systems beyond the 18 sampled."],
        "ac": [
            "GuidelineContentLoader resolves the ui-ux layer to the new files.",
            "accessibility.md states WCAG 2.2 AA.",
            "Samples run under docs/reference/uiux-samples/ and are store-registry allow-listed.",
        ],
        "dod": ["docs served; no derived file hand-edited.", "store-registry allow-globs present."],
        "files": ["docs/guidelines/ui-ux/design-principles.md", "docs/guidelines/ui-ux/anti-patterns.md",
                  "docs/guidelines/ui-ux/foundations.md", "docs/guidelines/ui-ux/components.md",
                  "docs/guidelines/ui-ux/patterns.md", "docs/guidelines/ui-ux/design-selection.md",
                  "docs/guidelines/ui-ux/implementation-stack.md", "docs/guidelines/ui-ux/trends-2026.md",
                  "docs/guidelines/ui-ux/accessibility.md", "docs/reference/uiux-samples/README.md",
                  "config/store-registry.json"],
        "value": 5, "effort": 5, "risk": 2, "moscow": "Should", "deps": [],
    },
    {
        "ext": f"{EXTERNAL}:catalog-engine",
        "title": "Design-system catalog store + selection engine (Go)",
        "problem": "No machine-readable mapping from product type to a design direction; tokens are hardcoded M3.",
        "goal": "PF can SELECT a ranked design direction from the idea.",
        "in_scope": [
            "New store config/design-systems.json (per system: product_types, style, stack, palette, radius/type/motion dials, component_set, a11y target).",
            "Go selection engine go/pfcore/design_system.go (REPORT 3 tree, ranked candidates).",
            "Expose design.select / design.catalog via core/go_host.py.",
        ],
        "out_scope": ["UI to browse the catalog (dashboard work, separate)."],
        "ac": [
            "config/design-systems.json is registered (kind:config, single writer).",
            "design.select returns 2-3 ranked candidates with rationale for a given product_type/domain.",
            "Selection logic lives in Go and passes language_rule_check.",
        ],
        "dod": ["Store registered; no Tier-1 palette leaks into components.", "Unit test for select()."],
        "files": ["config/design-systems.json", "go/pfcore/design_system.go",
                  "core/go_host.py", "config/store-registry.json"],
        "value": 5, "effort": 4, "risk": 2, "moscow": "Should", "deps": ["knowledge-ingestion"],
    },
    {
        "ext": f"{EXTERNAL}:token-engine",
        "title": "Design-token engine upgrade (3-tier OKLCH, light+dark)",
        "problem": "core/design_tokens.py ships fixed M3 defaults; no 3-tier architecture, no OKLCH, no direction seeding.",
        "goal": "Generate real design tokens from the selected direction.",
        "in_scope": [
            "Go token engine go/pfcore/design_tokens.go (global->alias->component, OKLCH ramps, light+dark, from a DesignDirection).",
            "Edit core/design_tokens.py to consume it while staying the single writer of tokens.json/tokens.css.",
        ],
        "out_scope": ["Multi-brand theming beyond the selected direction (later)."],
        "ac": [
            "Tokens emitted as 3 tiers with OKLCH + light/dark values.",
            "Seeded by the selected design direction.",
            "core/design_tokens.py remains the single writer of the token store.",
        ],
        "dod": ["Contrast validated per theme.", "Existing token callers unaffected (regression test)."],
        "files": ["go/pfcore/design_tokens.go", "core/design_tokens.py", "core/go_host.py"],
        "value": 4, "effort": 4, "risk": 2, "moscow": "Should", "deps": ["catalog-engine"],
    },
    {
        "ext": f"{EXTERNAL}:direction-stage",
        "title": "Dynamic design-direction stage + HIL suggest gate",
        "problem": "The pipeline never asks for or records a design direction.",
        "goal": "At the start of design, PF suggests ranked directions and the operator confirms one.",
        "in_scope": [
            "Add stage 1-0 'Design Direction' to pipeline-definition.json (depends on 0a/0e; feeds 1/1a/1c) with a HIL gate mirroring 10a/3a.",
            "Artifacts: docs/design-direction.md + design-spec.json; wire design.select.",
        ],
        "out_scope": ["Auto-approving without the operator."],
        "ac": [
            "Stage 1-0 exists with dependencies and a HIL suggest gate.",
            "docs/design-direction.md + design-spec.json are produced.",
            "Downstream stages consume the confirmed direction.",
        ],
        "dod": ["Gate blocks until confirmed; direction referenced by item_id.", "pipeline tests green."],
        "files": ["pipeline-definition.json", "docs/design-direction.md"],
        "value": 5, "effort": 3, "risk": 3, "moscow": "Should", "deps": ["catalog-engine", "token-engine"],
    },
    {
        "ext": f"{EXTERNAL}:skill-injection",
        "title": "Skill/guideline prompt injection (SKILLS: block)",
        "problem": "Python never injects skill bodies, so skills stay harness-bound.",
        "goal": "Agents receive applicable skills through PF's own prompt builder.",
        "in_scope": [
            "Edit core/orchestrator/agent_runner.py to add a SKILLS: block via the neutral resolver.",
            "Edit core/knowledge_compliance_checker.py GuidelineContentLoader to load skill bodies from pipeline/skills.",
            "Honor the skill-router token-budget protocol.",
        ],
        "out_scope": ["Changing agent model routing."],
        "ac": [
            "Prompt assembly adds a SKILLS: block for agents with skill bindings.",
            "Bodies load from pipeline/skills (neutral), not .opencode.",
            "Token budget enforced (skill-router tiers).",
        ],
        "dod": ["Agent prompt snapshot test asserts the SKILLS: block."],
        "files": ["core/orchestrator/agent_runner.py", "core/knowledge_compliance_checker.py",
                  "go/pfcore/skill_registry.go"],
        "value": 4, "effort": 3, "risk": 2, "moscow": "Should", "deps": ["skills-registry"],
    },
    {
        "ext": f"{EXTERNAL}:agent-bindings",
        "title": "Agent skill & knowledge-layer bindings",
        "problem": "UI agents declare empty skills:[] and only the 'frontend' layer.",
        "goal": "Bind the 8 skills + ui-ux/design-systems layers to the right agents.",
        "in_scope": [
            "Edit agents/*.agent.json (design, ux-ia, product-design-spec, implement-ui, design_critic, visual_qa, a11y-audit) with skills + knowledge_layers + allowed_inputs:design_direction.",
            "Mirror in config/agent-capabilities.json; regenerate agent cards.",
        ],
        "out_scope": ["New agents."],
        "ac": [
            "UI agents declare the relevant skills and ui-ux/design-systems layers.",
            "config/agent-capabilities.json mirrors the bindings.",
            "agent-card and role-prompt audits pass.",
        ],
        "dod": ["generate_agent_cards re-run; .opencode/agent/*.md in sync."],
        "files": ["agents/design.agent.json", "agents/ux-ia.agent.json",
                  "agents/implement-ui.agent.json", "agents/design_critic.agent.json",
                  "agents/visual_qa.agent.json", "agents/a11y-audit.agent.json",
                  "config/agent-capabilities.json"],
        "value": 4, "effort": 3, "risk": 2, "moscow": "Should", "deps": ["skills-registry", "skill-injection"],
    },
    {
        "ext": f"{EXTERNAL}:a11y-engine",
        "title": "Accessibility engine + fail-closed gate + templates",
        "problem": "No axe/pa11y/lighthouse engine; a11y-audit has no stage; accessibility templates are missing.",
        "goal": "WCAG 2.2 AA becomes a real fail-closed ship gate.",
        "in_scope": [
            "Go module go/pfcore/a11y_audit.go orchestrating axe/pa11y/lighthouse (Playwright) with a WCAG 2.2 AA verdict.",
            "Expose a11y.audit; add the a11y-audit pipeline stage; create test-framework/templates/accessibility/.",
        ],
        "out_scope": ["Manual assistive-tech testing (human task)."],
        "ac": [
            "a11y.audit returns a WCAG 2.2 AA verdict (fail-closed).",
            "a11y-audit wired as a blocking stage.",
            "test-framework/templates/accessibility/ exists.",
        ],
        "dod": ["Known-bad page FAILS the gate; known-good passes."],
        "files": ["go/pfcore/a11y_audit.go", "core/go_host.py", "pipeline-definition.json",
                  "test-framework/templates/accessibility/README.md"],
        "value": 5, "effort": 4, "risk": 2, "moscow": "Should", "deps": ["knowledge-ingestion"],
    },
    {
        "ext": f"{EXTERNAL}:design-qa",
        "title": "design_critic / visual_qa integration (anti-patterns + catalog + aesthetics)",
        "problem": "design_critic/visual_qa use shallow textual checks; the aesthetics skill is unused.",
        "goal": "QA validates against the chosen direction, non-negotiables and anti-patterns.",
        "in_scope": [
            "Edit core/design_critic.py (anti-patterns.md + non-negotiables + catalog conformance).",
            "Edit core/visual_qa.py to run visual-regression-aesthetics and compare vs direction + sample baselines.",
        ],
        "out_scope": ["Pixel-diff at scale in CI (baseline set grows later)."],
        "ac": [
            "design_critic flags catalog/anti-pattern violations.",
            "visual_qa executes the aesthetics skill against baselines.",
            "Findings reference the direction + item_id.",
        ],
        "dod": ["Synthetic violations are caught in tests."],
        "files": ["core/design_critic.py", "core/visual_qa.py"],
        "value": 4, "effort": 3, "risk": 2, "moscow": "Should", "deps": ["catalog-engine", "skill-injection"],
    },
]

WAVES = {
    "skills-registry": 1, "knowledge-ingestion": 1,
    "catalog-engine": 2, "skill-injection": 2, "a11y-engine": 2,
    "token-engine": 3, "agent-bindings": 3, "design-qa": 3,
    "direction-stage": 4,
}


def main() -> int:
    epic = backlog.add_epic(
        S, P, EPIC["title"],
        body=body(EPIC["problem"], EPIC["goal"], EPIC["in_scope"], EPIC["out_scope"], EPIC["ac"], EPIC["dod"]),
        type_="epic", origin="review", source=SRC, external_id=EPIC["ext"],
        value=EPIC["value"], effort=EPIC["effort"], risk=EPIC["risk"], moscow=EPIC["moscow"],
        acceptance_criteria=EPIC["ac"],
    )
    epic_id = epic["id"]
    print(f"epic {epic_id}: {epic['title']}")

    created = {}
    for it in ITEMS:
        full_dod = it["dod"] + UNIVERSAL_DOD
        row = backlog.add_epic(
            S, P, it["title"],
            body=body(it["problem"], it["goal"], it["in_scope"], it["out_scope"], it["ac"], it["dod"]),
            type_="feature", origin="review", source=SRC, external_id=it["ext"], epic=str(epic_id),
            value=it["value"], effort=it["effort"], risk=it["risk"], moscow=it["moscow"],
            acceptance_criteria=it["ac"],
        )
        created[it["ext"].split(":")[-1]] = row["id"]
        backlog.update(S, P, row["id"], affected_files=it["files"], verification=full_dod,
                       _note="planned affected files + DoD (design)")
        print(f"  {row['id']:12} {it['title']}")

    for it in ITEMS:
        eid = created[it["ext"].split(":")[-1]]
        deps = [{"task_id": created[d], "type": "REQUIRES", "required_state": "completed"}
                for d in it["deps"]]
        if deps:
            backlog.set_dependencies(S, P, eid, dependencies=deps)

    order = [{"id": created[k], "wave": WAVES[k], "status": "new"}
             for k in sorted(created, key=lambda x: WAVES[x])]
    backlog.set_execution_order(S, P, epic_id, order)
    print(f"execution order set on {epic_id}: {len(order)} items across 4 waves")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
