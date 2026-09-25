"""
Build framework-agnostic AgentSpec files from .opencode/agent/*.md cards,
merging Python contracts + criticality + knowledge layers. Authors specs for
pipeline agents that have no opencode card.

Output: agents/<id>.agent.json
"""
try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import os as _pf_os
    import sys as _pf_sys
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py')):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

import os
import sys

sys.path.insert(0, str(_PF_ROOT))

from core.agent_spec import AgentSpec, save_spec

CARDS_DIR = ".opencode/agent"
OUT_DIR = "agents"

KNOWLEDGE_LAYERS = {
    "ideation": ["business_logic"],
    "discovery": ["business_logic"],
    "design": ["api", "frontend", "backend"],
    "product-design-spec": ["frontend"],
    "design_critic": ["frontend"],
    "ux-ia": ["frontend"],
    "visual_qa": ["frontend"],
    "architect": ["api", "database", "backend"],
    "implement": ["api", "database", "frontend", "backend", "caching", "packaging"],
    "implement-db": ["database"],
    "implement-api": ["api", "backend"],
    "implement-logic": ["backend"],
    "implement-ui": ["frontend"],
    "code-review": ["api", "database", "frontend", "backend", "security"],
    "validate": ["testing"],
    "security": ["security"],
    "devops": ["packaging"],
    "package": ["packaging"],
    "document": ["packaging"],
    "orchestrator": ["business_logic"],
}

COMPLETION = {
    "implement": ["no_mock_or_stub", "no_todo", "builds"],
    "implement-db": ["no_mock_or_stub", "no_todo"],
    "implement-api": ["no_mock_or_stub", "no_todo"],
    "implement-logic": ["no_mock_or_stub", "no_todo"],
    "implement-ui": ["no_mock_or_stub", "no_todo"],
    "devops": ["no_todo"],
    "package": ["no_todo"],
    "validate": ["tests_exist", "tests_pass"],
    "code-review": ["no_critical_findings"],
    "security": ["no_critical_findings"],
}

# Code-oriented agents that must be able to write files even if their card
# lacks an explicit permission block.
DEFAULT_CODE_TOOLS = ["list_dir", "read_file", "run_command", "write_file"]
FORCE_TOOLS = {"implement", "implement-db", "implement-api", "implement-logic",
               "implement-ui", "devops", "package", "fix"}

# Agents the pipeline needs that have no opencode card -> author minimal specs.
AUTHORED = {
    "design_critic": ("Review the design for quality and completeness.",
                      "You are the Design Critic. Review docs/design.md and docs/requirements.md.\n"
                      "Check: coverage of all features, feasibility, clarity, and consistency.\n"
                      "Output a verdict (PASS/FAIL) and specific, actionable findings."),
    "discovery": ("Run structured discovery to shape the product.",
                  "You are the Discovery agent. From the brief, produce domain analysis, stakeholder map,\n"
                  "user personas, and an end-to-end user journey. Keep it concrete and grounded."),
    "product-design-spec": ("Produce a structured product design specification.",
                            "You are the Product Design Spec agent. Produce a precise, implementation-ready\n"
                            "spec: screens/flows, components, states, and data. No placeholders."),
    "ux-ia": ("Define UX and information architecture + design tokens.",
              "You are the UX/IA agent. Produce navigation/IA, key flows, and design tokens\n"
              "(color, spacing, typography) suitable for implementation."),
    "visual_qa": ("Verify rendered UI against the design spec.",
                  "You are the Visual QA agent. Compare the produced UI against docs/design.md and\n"
                  "design tokens. Report concrete visual defects with severity."),
}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    written = []

    # 1) from opencode cards
    if os.path.isdir(CARDS_DIR):
        for fn in sorted(os.listdir(CARDS_DIR)):
            if not fn.endswith(".md"):
                continue
            spec = AgentSpec.from_opencode_card(os.path.join(CARDS_DIR, fn))
            spec.merge_contract()
            spec.knowledge_layers = KNOWLEDGE_LAYERS.get(spec.id, [])
            spec.completion = COMPLETION.get(spec.id, [])
            if spec.id in FORCE_TOOLS and not spec.tools:
                spec.tools = list(DEFAULT_CODE_TOOLS)
            if spec.id in ("implement",):
                spec.sub_agents = ["implement-db", "implement-api", "implement-logic", "implement-ui"]
            save_spec(spec, OUT_DIR)
            written.append(spec.id)

    # 2) author missing pipeline agents
    for aid, (desc, instructions) in AUTHORED.items():
        if os.path.exists(os.path.join(OUT_DIR, f"{aid}.agent.json")):
            continue
        spec = AgentSpec(id=aid, name=aid.replace("-", " ").title(), description=desc,
                         instructions=instructions, mode="subagent",
                         knowledge_layers=KNOWLEDGE_LAYERS.get(aid, []),
                         completion=COMPLETION.get(aid, []))
        spec.merge_contract()
        save_spec(spec, OUT_DIR)
        written.append(aid)

    print(f"Wrote {len(written)} agent specs to {OUT_DIR}/")
    print("  " + ", ".join(sorted(written)))


if __name__ == "__main__":
    main()
