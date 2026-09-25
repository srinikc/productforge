#!/usr/bin/env python3
"""Generate the pipeline stages & agents reference doc (+ PDF).

Source of truth: pipeline-definition.json + agents/*.agent.json. The markdown is
DERIVED — never hand-edit it; re-run this script instead.

Usage:  python scripts/gen_pipeline_reference.py
Output: docs/PIPELINE-STAGES-REFERENCE.md (+ .pdf)
"""
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_MD = os.path.join(REPO, "docs", "PIPELINE-STAGES-REFERENCE.md")

# Stage-specific outputs beyond the canonical artifacts/<stage>/<agent>-output.md
EXTRA = {
    "0": ["docs/product-plan.md"],
    "0a": ["docs/idea-refined.md", "docs/domain-analysis.md", "docs/stakeholder-map.md",
           "docs/user-personas.md", "discovery-panel.json", "discovery-questions.json"],
    "0b": ["product-plan.json"],
    "0c": ["marketing-strategy/positioning.md"],
    "0e": ["marketing-strategy/gtm-strategy.md", "marketing-strategy/campaign-plan.md"],
    "1": ["docs/design.md", "docs/requirements.md", "artifacts/1/features/F-*-functional.md"],
    "1a": ["design-spec.json"],
    "2": ["docs/architecture.md"],
    "8": ["docs/* (README / guides / API)"],
    "9": ["dist/* (installers / packages)"],
}


def _card(agent):
    try:
        return json.load(open(os.path.join(REPO, "agents", f"{agent}.agent.json"),
                              encoding="utf-8"))
    except Exception:
        return {}


def _role(agent):
    c = _card(agent)
    d = (c.get("description") or c.get("name") or "").strip()
    d = re.sub(r"^[A-Za-z _-]+ agent\.\s*", "", d)
    return d.split(". ")[0][:150]


def _dkey(s):
    m = re.match(r"S(\d+)\.(\d+)([a-z]?)", s or "")
    return (int(m.group(1)), int(m.group(2)), m.group(3)) if m else (99, 99, "")


def main() -> int:
    d = json.load(open(os.path.join(REPO, "pipeline-definition.json"), encoding="utf-8"))
    stages = d["stages"]
    ordered = sorted(stages.items(), key=lambda kv: _dkey(kv[1].get("display_id", "")))

    L = []
    L.append("# Product Forge — Pipeline Stages & Agents Reference")
    L.append("")
    L.append("> **Generated** from `pipeline-definition.json` + `agents/*.agent.json` "
             "(`scripts/gen_pipeline_reference.py`). Do not hand-edit — re-run the generator.")
    L.append("")
    L.append(f"**{len(ordered)} stages** across the phases below. Every stage's canonical "
             "artifact is `artifacts/<stage>/<agent>-output.md`; extra formats "
             "(.html/.pdf/.xlsx) are derived per `config/artifact-formats.json`. Stage "
             "directories use human-readable names (`<id> - <Name>`, e.g. `1 - Design`) per "
             "`config/artifact-paths.json`; each holds a `_stage.json` and the tree has an "
             "`artifacts/INDEX.md` (3a).")
    L.append("")

    # phase summary
    phases = {}
    for sid, st in ordered:
        phases.setdefault(st.get("phase", "?"), []).append(sid)
    L.append("## Phases")
    L.append("")
    L.append("| Phase | Stages |")
    L.append("| --- | --- |")
    for ph, ids in phases.items():
        L.append(f"| {ph} | {', '.join(ids)} |")
    L.append("")

    # stage table
    L.append("## Stages")
    L.append("")
    L.append("| Stage | Disp | Name | Phase | Agent(s) | Role | Artifact(s) | Prev → Next | Opt | Gate |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for i, (sid, st) in enumerate(ordered):
        agents = st.get("ideal_flow") or []
        art = [f"`artifacts/{sid}/{a}-output.md`" for a in agents] + \
              [f"`{x}`" for x in EXTRA.get(sid, [])]
        prev = ordered[i - 1] if i > 0 else None
        nxt = ordered[i + 1] if i + 1 < len(ordered) else None
        prev_s = f"{prev[0]}" if prev else "—"
        next_s = f"{nxt[0]}" if nxt else "—"
        role = " / ".join(_role(a) for a in agents)
        opt = "yes" if st.get("optional") else ""
        gate = st.get("approval_gate") or ""
        L.append(f"| **{sid}** | {st.get('display_id','')} | {st.get('name','')} | "
                 f"{st.get('phase','')} | {', '.join('`'+a+'`' for a in agents)} | {role} | "
                 f"{' '.join(art)} | {prev_s} → {next_s} | {opt} | {gate} |")
    L.append("")

    # agent reference
    L.append("## Agent reference")
    L.append("")
    L.append("| Agent | Role | Stages |")
    L.append("| --- | --- | --- |")
    used = {}
    for sid, st in ordered:
        for a in (st.get("ideal_flow") or []):
            used.setdefault(a, []).append(sid)
    for a in sorted(used):
        L.append(f"| `{a}` | {_role(a)} | {', '.join(used[a])} |")
    L.append("")

    # notes
    L.append("## Notes")
    L.append("")
    L.append("- **Optional stages** (`0b`, `0c`, `0d`, `0e`, `13`, `13a`, `13b`) are enabled "
             "or disabled per project by `core/pipeline_tailoring.py` (idea-signal based) and "
             "recorded in `pipeline-plan.json` (`enabled_optional` / `disabled_optional`).")
    L.append("- **Display sequence vs canonical id:** `pipeline-plan.json.display` maps a "
             "runtime `display_seq` (e.g. `S2.1`) to a `canonical_id` (e.g. `S3.1`) because the "
             "visible numbering shifts when optional stages are toggled. The canonical id is the "
             "stable reference.")
    L.append("- **Capability generators vs stages:** some outputs (`marketing-strategy/*`, "
             "`onboarding/*`, `presentations/*`, `videos/*`, `product-plan.json`) are produced by "
             "capability modules (`core/marketing.py`, `core/customer_onboarding.py`, "
             "`core/presentation_generator.py`, `core/product_plan.py`) run as stage hooks — "
             "independent of stages `0b–0e`.")
    L.append("- **Spec ids** (FR/NFR/US + local families) are parsed by the single canonical "
             "query `core/id_index.py`; id families live in `config/spec-id-families.json`. "
             "Feature ids are a running number across features (no hard cap): F-1 `FR-1..n`, "
             "F-2 `n+1..`, via `core/id_index.renumber_global`.")
    L.append("- **Single-run guard:** `core/run_guard.py` stops any live instance before a "
             "start/restart/resume/continue and takes the project lock (`products/.locks/`).")
    L.append("- **run_id linkage:** approvals carry `run_id`; `core/run_state.py` records run "
             "attempts in `pipeline-runs.json` and reconciles already-approved stages on resume "
             "(preserve-first — user data is never cleared).")
    L.append("")

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))
    print("wrote", os.path.relpath(OUT_MD, REPO))

    # derive PDF
    try:
        sys.path.insert(0, REPO)
        from core import artifact_formats as af
        content = open(OUT_MD, encoding="utf-8").read()
        fmts = af.formats_for("product-forge", "document", "ref", kind="report", content=content)
        af.emit("product-forge", OUT_MD, [f for f in fmts if f in ("md", "pdf")], content=content,
                agent_id="document")
    except Exception as e:
        print("pdf derive skipped:", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
