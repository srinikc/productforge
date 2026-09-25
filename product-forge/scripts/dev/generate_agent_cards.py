"""
Generate standardized agent cards (.opencode/agent/<id>.md) from AgentSpec files,
following docs/AGENT_CONTRACT_STANDARD.md (frontmatter + sections 0-8).

Output goes to a preview dir by default (does NOT overwrite originals):
  python scripts/dev/generate_agent_cards.py [--out .opencode/agent_std] [--apply]
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

SPECS_DIR = os.path.join(ROOT, "agents")
PIPELINE = os.path.join(ROOT, "pipeline-definition.json")

CODE_ARTIFACTS = {
    "implement": ["src/<package>/ (all modules)", "tests/", "pyproject.toml or requirements.txt"],
    "implement-db": ["src/<package>/db.py or models/", "migrations/"],
    "implement-api": ["src/<package>/api/"],
    "implement-logic": ["src/<package>/service.py"],
    "implement-ui": ["src/<package>/ui/ or app/"],
    "devops": ["Dockerfile", "docker-compose.yml", "CI config", "build scripts"],
    "package": ["dist/", "installers", "BOM.md", "RELEASE.md"],
    "fix": ["fixed source files", "regression test"],
}
DOC_ARTIFACTS = {
    "ideation": ["docs/product-plan.md"],
    "discovery": ["docs/discovery.md"],
    "design": ["docs/requirements.md", "docs/design.md"],
    "product-design-spec": ["docs/product-design-spec.md", "docs/design-tokens.json"],
    "design_critic": ["docs/design-review.md"],
    "ux-ia": ["docs/ux-ia.md", "docs/design-tokens.json"],
    "architect": ["docs/architecture.md"],
    "code-review": ["reports/code-review.md"],
    "validate": ["reports/issues.md", "reports/test-report.md"],
    "security": ["reports/security-report.md"],
    "document": ["README.md", "docs/USER_GUIDE.md", "docs/API.md"],
    "orchestrator": ["PROJECT-STATUS.md", "pipeline-state.json"],
    "visual_qa": ["reports/visual-qa.md"],
}


def field(obj, name, default):
    return obj.get(name, default)


def clean_description(d):
    """Strip framework-specific (opencode) orchestration phrases."""
    parts = [p.strip() for p in (d or "").replace("\n", " ").split(".") if p.strip()]
    keep = [p for p in parts if not any(k in p.lower() for k in
            ("orchestrate", "sub-agent", "subagent", "task tool"))]
    txt = ". ".join(keep[:2]) if keep else (d or "")
    return (txt + ".") if txt and not txt.endswith(".") else txt


def gen_frontmatter(spec, stages, model=""):
    perm = {"bash": "allow" if "run_command" in spec["tools"] else "deny",
            "edit": "allow" if "write_file" in spec["tools"] else "deny",
            "web": "allow" if "http_get" in spec["tools"] else "deny"}
    desc = clean_description(spec.get("description", "")) or (spec["id"] + " agent")
    lines = [
        "---",
        f"description: {desc}",
        f"mode: {spec.get('mode','subagent')}",
        f"model: {model or 'opencode-go/mimo-v2.5'}",
        f"agent_id: {spec['id']}",
        "version: 1.0.0",
        'spec_version: "1.0"',
        "permission:",
        f"  bash: {perm['bash']}",
        f"  edit: {perm['edit']}",
        f"  web: {perm['web']}",
    ]
    skills = spec.get("skills") or []
    if skills:
        lines.append("  skill:")
        for s in skills:
            lines.append(f'    "{s}": allow')
    lines.append("---")
    return "\n".join(lines)


def gen_body(spec, stages):
    sid = spec["id"]
    artifacts = CODE_ARTIFACTS.get(sid) or DOC_ARTIFACTS.get(sid) or ["(role-specific outputs)"]
    stages_for = [s for s in stages if sid in stages[s].get("ideal_flow", [])]
    lines = [f"# {spec.get('name', sid)}", ""]

    lines += ["## 0. METADATA", f"- **Agent ID**: {sid}",
              "- **Version**: 1.0.0", "- **Spec Version**: 1.0",
              f"- **Model tier**: {spec.get('model_tier','medium')}",
              f"- **Tools**: {', '.join(spec.get('tools') or []) or 'none (markdown)'}",
              f"- **Stages**: {', '.join(stages_for) or '-'}", ""]

    lines += ["## 1. ROLE", clean_description(spec.get("description", "")) or f"{sid} agent.", "",
              "- Decides: own stage outputs",
              "- Does NOT reduce scope, use mocks, or write outside the workspace", ""]

    lines += ["## 2. INPUTS",
              f"- Allowed: {', '.join(spec.get('allowed_inputs') or []) or 'prior-stage artifacts'}",
              f"- Forbidden: {', '.join(spec.get('forbidden_inputs') or []) or 'unrelated files'}", ""]

    lines += ["## 3. OUTPUTS",
              f"- Format: {spec.get('output_format','markdown')}",
              f"- Contract: max_input={spec.get('max_input_tokens')} max_output={spec.get('max_output_tokens')}", ""]

    rules = ["- No mocks, TODOs, placeholders, or `pass` in production output.",
             "- Respect the declared tech stack and scope (SCOPE guard)."]
    for c in spec.get("completion") or []:
        rules.append(f"- Completion: {c}")
    lines += ["## 4. RULES"] + rules + [""]

    if spec.get("tools"):
        wf = ["1. Read only the listed inputs.", 
              "2. Create real files with `write_file` (use `run_command` to run tests/build).",
              "3. Do NOT explore with `list_dir`/`read_file`/`ls` — write first.",
              "4. Return a short final summary."]
    else:
        wf = ["1. Read only the listed inputs.", "2. Produce the required markdown output.",
              "3. Return a short final summary."]
    lines += ["## 5. WORKFLOW"] + wf + [""]

    lines += ["## 6. ARTIFACTS"] + [f"- {a}" for a in artifacts] + [""]

    checks = spec.get("completion") or ["output present and consistent with inputs"]
    lines += ["## 7. QUALITY CHECKS"] + [f"- {c}" for c in checks] + [""]

    state = ["- Append an entry to `docs/agent-audit.md`.",
             "- Update `docs/agent-context.md` with current stage/agent/pending."]
    if sid.startswith("implement"):
        state.append("- Update `docs/feature-status.md` for implemented features.")
    lines += ["## 8. STATE UPDATES"] + state + [""]

    lines += ["## 9. REPOSITORY RULES (binding)",
              "- Product Forge naming only (the legacy `fac`+`tory` token is prohibited in code/config).",
              "- Work items only via `core/backlog.py`; one truth per concern / one writer per file;",
              "  reference by `item_id`/`feature_id`, never copy.",
              "- Before adding anything follow `docs/ADDING-TO-PRODUCT-FORGE.md`; register stores in",
              "  `config/store-registry.json`; run `python scripts/dev/wired_audit.py` (must exit 0).", ""]

    # Preserve the original rich instructions verbatim (no capability loss).
    instr = (spec.get("instructions") or "").strip()
    if instr:
        lines += ["---", "", "<!-- ===== ORIGINAL AGENT INSTRUCTIONS (verbatim) ===== -->", "", instr, ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, ".opencode", "agent_std"))
    ap.add_argument("--apply", action="store_true", help="write into .opencode/agent (overwrite)")
    args = ap.parse_args()

    with open(PIPELINE, encoding="utf-8-sig") as f:
        stages = json.load(f).get("stages", {})

    # model ids come from the shared tier config (config-driven, not hardcoded)
    tier = {}
    tp = os.path.join(ROOT, "config", "model-tier.json")
    if os.path.exists(tp):
        try:
            with open(tp, encoding="utf-8-sig") as f:
                tier = json.load(f)
        except Exception:
            tier = {}
    tier_agents = tier.get("agents", {})

    out = os.path.join(ROOT, ".opencode", "agent") if args.apply else args.out
    os.makedirs(out, exist_ok=True)
    n = 0
    for fn in sorted(os.listdir(SPECS_DIR)):
        if not fn.endswith(".agent.json"):
            continue
        with open(os.path.join(SPECS_DIR, fn), encoding="utf-8") as f:
            spec = json.load(f)
        at = tier_agents.get(spec["id"], {})
        model = f"{at.get('provider','opencode-go')}/{at.get('model','mimo-v2.5')}"
        card = gen_frontmatter(spec, stages, model) + "\n\n" + gen_body(spec, stages) + "\n"
        with open(os.path.join(out, f"{spec['id']}.md"), "w", encoding="utf-8") as f:
            f.write(card)
        n += 1
    print(f"Generated {n} standardized cards -> {out}")


if __name__ == "__main__":
    main()
