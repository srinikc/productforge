"""Per-agent brief summaries — written at AGENT COMPLETION (not gated behind approvals).

Each agent's output is distilled to a short structured digest the moment the agent
finishes:
  docs/agent-summaries/<stage>-<agent>.md
  docs/agent-summaries/INDEX.md            (all agents, in order)

These roll up into the final report (`reporting.generate_final_report`), so the final
report always contains what each agent did. Owner: this module (single writer).
"""
import glob
import os
from datetime import datetime
from typing import Dict

_SUBDIR = os.path.join("docs", "agent-summaries")


def _summarizer():
    try:
        from core.orchestrator.storage import ArtifactSummarizer
        return ArtifactSummarizer
    except Exception:
        return None


def summarize_text(text: str) -> str:
    S = _summarizer()
    if S is None:
        return text or ""
    try:
        return S.summarize(text or "", max_chars=0)
    except Exception:
        return text or ""


def write_summary(project_dir: str, stage_id: str, agent_id: str,
                  content: str, status: str = "completed") -> str:
    """Write (or refresh) docs/agent-summaries/<stage>-<agent>.md + INDEX.md."""
    d = os.path.join(project_dir, _SUBDIR)
    os.makedirs(d, exist_ok=True)
    digest = summarize_text(content)
    p = os.path.join(d, f"{stage_id}-{agent_id}.md")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# {stage_id} {agent_id} — brief summary\n\n"
                f"> status: {status} · generated {datetime.now().isoformat(timespec='seconds')}\n\n"
                f"{digest.strip()}\n")
    _refresh_index(project_dir)
    return p


def _refresh_index(project_dir: str) -> None:
    d = os.path.join(project_dir, _SUBDIR)
    if not os.path.isdir(d):
        return
    lines = ["# Agent summaries index", "",
             "> Generated at each agent completion. Rolls into final-report.json.", ""]
    for p in sorted(glob.glob(os.path.join(d, "*.md"))):
        if os.path.basename(p) == "INDEX.md":
            continue
        lines.append(f"- [{os.path.basename(p)[:-3]}]({os.path.basename(p)})")
    with open(os.path.join(d, "INDEX.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def read_all(project_dir: str) -> Dict[str, str]:
    """{ '<stage>-<agent>': summary_text } for the final report."""
    d = os.path.join(project_dir, _SUBDIR)
    out: Dict[str, str] = {}
    for p in sorted(glob.glob(os.path.join(d, "*.md"))):
        if os.path.basename(p) == "INDEX.md":
            continue
        try:
            out[os.path.basename(p)[:-3]] = open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            pass
    return out
