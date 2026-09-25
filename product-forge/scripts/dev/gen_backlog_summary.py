"""Generate docs/BACKLOG-SUMMARY.md for both scopes (regenerable)."""
import os
from datetime import datetime
from core import backlog

OUT = "docs/BACKLOG-SUMMARY.md"

# category rules: (label, predicate on external_id/title)
def cat(it):
    e = (it.get("external_id") or "") + " " + (it.get("title") or "")
    e = e.lower()
    if "wire-orphan" in e or "retire-candidate" in e:
        return "Orphan wiring / retire"
    if "phase-business" in e or "phase-operate" in e or "stages 0b" in e or "stages 13" in e:
        return "Phases (new)"
    if any(k in e for k in ("tailor", "template", "dynamic-agent", "model-tier", "runtime-integration",
                            "roster", "capability-binding", "api-first")):
        return "Dynamic pipeline / agents"
    if any(k in e for k in ("knowledge", "business-models", "techstack", "research", "ingest")):
        return "Knowledge / KB"
    if any(k in e for k in ("per-feature", "diagram", "spec", "cache", "context", "prompt-stable",
                            "delegation-context", "parallel", "bound-loops", "artifact-format", "artifact-render",
                            "stale-artifacts")):
        return "Specs / cache / context / artifacts"
    if any(k in e for k in ("api", "metrics", "blueprint", "git", "report", "ledger", "hil", "idea-consol",
                            "ai-integration", "time-budget", "pdf-env")):
        return "API / reports / HIL / misc"
    if any(k in e for k in ("intake", "discovery", "hil-prompt", "prompt", "approval", "timeout")):
        return "Discovery / HIL / prompts"
    if "licen" in e or "tenant" in e or "entitle" in e or "seat" in e or "trial" in e or "rbac" in e:
        return "Licensing / tenancy"
    if "model" in e and "fit" in e:
        return "Model fit"
    if it.get("type") == "bug":
        return "Bug fixes"
    return "Wiring / tech-debt / API"


def render(scope, project=None, title=""):
    op = backlog.list_open(scope, project)
    cl = backlog.list_closed(scope, project)
    by_status = {}
    for it in op:
        by_status.setdefault(it.get("status", "new"), []).append(it)

    L = [f"## {title} (`{backlog.qualify(scope, project, 'BI-0000').rsplit(':',1)[0]}`)", ""]
    L.append(f"- **Open:** {len(op)}  |  **Closed:** {len(cl)}")
    for st, arr in sorted(by_status.items()):
        L.append(f"- `{st}`: {len(arr)}")
    L.append("")

    # verifying / parked first, then new by category
    for st in ("verifying", "parked"):
        arr = by_status.get(st, [])
        if not arr:
            continue
        L.append(f"### {st} ({len(arr)})")
        L.append("| ID | MoSCoW | Type | Title |")
        L.append("|---|---|---|---|")
        for it in sorted(arr, key=lambda e: int(e["id"].split("-")[1])):
            L.append(f"| {it['id']} | {it.get('moscow')} | {it.get('type')} | {it.get('title')} |")
        L.append("")

    news = by_status.get("new", [])
    groups = {}
    for it in news:
        groups.setdefault(cat(it), []).append(it)
    L.append(f"### new, by category ({len(news)})")
    for g in sorted(groups):
        arr = sorted(groups[g], key=lambda e: int(e["id"].split("-")[1]))
        L.append(f"**{g}** ({len(arr)})")
        L.append("| ID | MoSCoW | Type | Title |")
        L.append("|---|---|---|---|")
        for it in arr:
            L.append(f"| {it['id']} | {it.get('moscow')} | {it.get('type')} | {it.get('title')} |")
        L.append("")
    return L, len(op), len(cl)


def main():
    L = ["# Backlog Summary", "",
         f"> GENERATED {datetime.now().isoformat(timespec='seconds')} by `scripts/dev/gen_backlog_summary.py`.",
         "> Derived file - do not hand-edit. Truth: the backlog stores (core/backlog.py).", ""]
    b, bo, bc = render("product_forge", None, "Pipeline backend (product_forge)")
    L += b + ["---", ""]
    d, do, dc = render("project", "ProductForge-Dashboard", "Dashboard (ProductForge-Dashboard)")
    L += d + ["---", "",
              "## Totals", f"- backend: {bo} open / {bc} closed", f"- dashboard: {do} open / {dc} closed", ""]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))
    print("wrote", OUT, "| backend", bo, "| dash", do)


if __name__ == "__main__":
    main()
