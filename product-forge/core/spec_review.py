"""
QA Spec Review gate (pre-implementation, stage 3a).

QA reviews every design/architect/UX artifact one-by-one, classifies findings as
BLOCKING or OPTIONAL/MINOR, tracks resolution, and routes findings to the owning
agent. Blocking findings prevent implementation; optional findings go to HIL.

Persistence:
  test-framework/results/<project>/spec-review.json      (machine-readable)
  products/<project>/docs/qa/reviews/<artifact>-review.md
  products/<project>/docs/qa/review-summary.md

Evidence-based, rules-first (LLM review can be layered on later).
"""
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TF = os.path.join(_REPO, "test-framework")

# artifact rel path -> (owning agent, required?)
ARTIFACTS: Dict[str, tuple] = {
    "docs/requirements.md": ("design", True),
    "docs/design.md": ("design", True),
    "docs/architecture.md": ("architect", True),
    "docs/product-design-spec.md": ("product-design-spec", False),
    "docs/ux-ia.md": ("ux-ia", False),
    "docs/infra.json": ("architect", False),
}

_FR = re.compile(r"\bFR[-_]?\d+\b", re.I)
_NFR = re.compile(r"\bNFR[-_]?\d+\b", re.I)
_PLACEHOLDER = re.compile(r"\b(TODO|TBD|FIXME|placeholder|lorem ipsum)\b", re.I)


def _project_name(project_dir: str) -> str:
    return os.path.basename(os.path.normpath(project_dir))


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _finding(idx: int, artifact: str, owner: str, cls: str, severity: str,
             category: str, location: str, recommendation: str,
             requirement_id: str = "") -> Dict[str, Any]:
    return {
        "id": f"SR-{idx:03d}",
        "artifact": artifact,
        "owner": owner,
        "class": cls,            # BLOCKING | OPTIONAL | MINOR | QUESTION
        "severity": severity,    # critical | high | medium | low
        "category": category,    # completeness | consistency | testability | usability | ...
        "location": location,
        "recommendation": recommendation,
        "requirement_id": requirement_id,
        "status": "open",        # open -> responded -> resolved -> verified | waived
        "resolution_notes": "",
        "evidence": "",
        "hil_decision": "",
        "updated_at": datetime.now().isoformat(),
    }


def _review_one(artifact: str, owner: str, text: str, idx: int,
                required: bool = True) -> (List[Dict], int):
    fs: List[Dict] = []

    def add(**kw):
        nonlocal idx
        idx += 1
        fs.append(_finding(idx, artifact, owner, **kw))

    if not text.strip():
        if required:
            add(cls="BLOCKING", severity="critical", category="completeness",
                location="(whole file)", recommendation="Artifact is missing or empty.")
        else:
            add(cls="OPTIONAL", severity="medium", category="completeness",
                location="(whole file)", recommendation="Optional artifact not provided.")
        return fs, idx

    if len(text) < 200:
        add(cls="BLOCKING", severity="high", category="completeness",
            location="(whole file)",
            recommendation="Artifact is too thin to be implementable/testable.")

    ph = _PLACEHOLDER.search(text)
    if ph:
        add(cls="OPTIONAL", severity="low", category="completeness",
            location=ph.group(0),
            recommendation=f"Resolve placeholder '{ph.group(0)}' before release.")

    low = text.lower()

    if artifact == "docs/requirements.md":
        fr, nfr = set(_FR.findall(text)), set(_NFR.findall(text))
        if not fr:
            add(cls="BLOCKING", severity="high", category="requirements-coverage",
                location="Functional Requirements",
                recommendation="No FR-* functional requirements defined.")
        if not nfr:
            add(cls="BLOCKING", severity="high", category="requirements-coverage",
                location="Non-Functional Requirements",
                recommendation="No NFR-* non-functional requirements defined.")
        if "acceptance" not in low:
            add(cls="BLOCKING", severity="high", category="testability",
                location="requirements",
                recommendation="Add measurable acceptance criteria per FR/NFR (testability).")

    if artifact in ("docs/design.md", "docs/product-design-spec.md"):
        if "acceptance" not in low:
            add(cls="BLOCKING", severity="high", category="testability",
                location="design spec",
                recommendation="Design must state acceptance criteria per feature.")
        if not (_FR.search(text) or _NFR.search(text)):
            add(cls="OPTIONAL", severity="medium", category="consistency",
                location="design spec",
                recommendation="Link each feature to its FR/NFR id for traceability.")

    if artifact == "docs/ux-ia.md":
        if "accessib" not in low:
            add(cls="OPTIONAL", severity="medium", category="usability",
                location="UX/IA spec",
                recommendation="Address accessibility (WCAG) + empty/error/loading states.")

    if artifact == "docs/architecture.md":
        if not any(k in low for k in ("performance", "security", "scalab", "reliab")):
            add(cls="OPTIONAL", severity="medium", category="architecture",
                location="architecture",
                recommendation="Tie architecture to NFRs (perf/security/scalability/reliability).")
        if "component" not in low:
            add(cls="OPTIONAL", severity="low", category="completeness",
                location="architecture",
                recommendation="List components/services and their interfaces.")

    if artifact == "docs/infra.json":
        try:
            data = json.loads(text)
            if not (data.get("kind") or data.get("runtime")):
                add(cls="OPTIONAL", severity="medium", category="deployability",
                    location="infra.json",
                    recommendation="Specify kind/runtime for deploy/test environments.")
        except Exception:
            add(cls="BLOCKING", severity="high", category="consistency",
                location="infra.json",
                recommendation="infra.json is not valid JSON.")

    return fs, idx


def review_all(project_dir: str, project: Optional[str] = None,
               llm_review: Optional[Any] = None) -> Dict[str, Any]:
    """Review every spec artifact; persist findings; return the summary.

    `llm_review(artifact, text) -> list[str]` adds OPTIONAL advisory findings when
    provided (opt-in, e.g. PIPELINE_SPEC_LLM=1).
    """
    project = project or _project_name(project_dir)
    idx = 0
    reviews: List[Dict] = []
    for artifact, meta in ARTIFACTS.items():
        owner, required = (meta if isinstance(meta, tuple) else (meta, True))
        path = os.path.join(project_dir, artifact)
        text = _read(path)
        fs, idx = _review_one(artifact, owner, text, idx, required=required)
        if callable(llm_review) and text.strip():
            try:
                for rec in (llm_review(artifact, text) or [])[:8]:
                    if not rec:
                        continue
                    idx += 1
                    fs.append(_finding(idx, artifact, owner, cls="OPTIONAL", severity="low",
                                       category="llm-review", location="(LLM review)",
                                       recommendation=str(rec)[:400]))
            except Exception:
                pass
        status = "changes_requested" if any(f["class"] == "BLOCKING" for f in fs) else \
                 ("approved_with_notes" if fs else "approved")
        reviews.append({
            "artifact": artifact,
            "owner": owner,
            "path": path,
            "status": status,
            "present": os.path.exists(path),
            "findings": fs,
        })

    blocking = [f for r in reviews for f in r["findings"] if f["class"] == "BLOCKING"]
    optional = [f for r in reviews for f in r["findings"] if f["class"] in ("OPTIONAL", "MINOR")]
    summary = {
        "project": project,
        "iteration": datetime.now().isoformat(),
        "reviews": reviews,
        "summary": {
            "blocking_open": len(blocking),
            "optional_open": len(optional),
            "resolved": 0,
            "waived": 0,
            "rag": "red" if blocking else ("yellow" if optional else "green"),
        },
    }
    _persist(project_dir, project, summary)
    return summary


def _persist(project_dir: str, project: str, data: Dict):
    # console JSON
    out_dir = os.path.join(_TF, "results", project)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "spec-review.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    # rendered markdown for reference
    qa_dir = os.path.join(project_dir, "docs", "qa")
    rev_dir = os.path.join(qa_dir, "reviews")
    os.makedirs(rev_dir, exist_ok=True)
    for r in data["reviews"]:
        name = os.path.basename(r["artifact"]).replace(".", "-")
        lines = [f"# QA Spec Review — {r['artifact']}",
                 f"- owner: {r['owner']}", f"- status: {r['status']}", ""]
        if not r["findings"]:
            lines.append("No findings.")
        for f in r["findings"]:
            lines.append(f"- [{f['class']}/{f['severity']}] {f['id']} ({f['category']}) "
                         f"@ {f['location']}: {f['recommendation']}")
        with open(os.path.join(rev_dir, f"{name}-review.md"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    s = data["summary"]
    with open(os.path.join(qa_dir, "review-summary.md"), "w", encoding="utf-8") as fh:
        fh.write(f"# QA Spec Review Summary\n\n"
                 f"- blocking open: {s['blocking_open']}\n- optional open: {s['optional_open']}\n"
                 f"- RAG: {s['rag']}\n")


def summary(project_dir: str, project: Optional[str] = None) -> Dict[str, Any]:
    project = project or _project_name(project_dir)
    path = os.path.join(_TF, "results", project, "spec-review.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("summary", {})
    except Exception:
        return {}


def blocking_open(project_dir: str, project: Optional[str] = None) -> bool:
    return summary(project_dir, project).get("blocking_open", 0) > 0


def update_finding(project_dir: str, finding_id: str, status: str,
                   resolution_notes: str = "", hil_decision: str = "",
                   project: Optional[str] = None) -> bool:
    """Update a finding's resolution status (open/resolved/verified/waived)."""
    project = project or _project_name(project_dir)
    path = os.path.join(_TF, "results", project, "spec-review.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return False
    changed = False
    for r in data.get("reviews", []):
        for f in r.get("findings", []):
            if f["id"] == finding_id:
                f["status"] = status
                f["resolution_notes"] = resolution_notes or f.get("resolution_notes", "")
                if hil_decision:
                    f["hil_decision"] = hil_decision
                f["updated_at"] = datetime.now().isoformat()
                changed = True
    if changed:
        # recompute summary counts
        all_f = [f for r in data["reviews"] for f in r["findings"]]
        blocking = [f for f in all_f if f["class"] == "BLOCKING" and f["status"] not in ("resolved", "verified", "waived")]
        optional = [f for f in all_f if f["class"] in ("OPTIONAL", "MINOR") and f["status"] not in ("resolved", "verified", "waived")]
        data["summary"] = {
            "blocking_open": len(blocking),
            "optional_open": len(optional),
            "resolved": len([f for f in all_f if f["status"] in ("resolved", "verified")]),
            "waived": len([f for f in all_f if f["status"] == "waived"]),
            "rag": "red" if blocking else ("yellow" if optional else "green"),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    return changed
