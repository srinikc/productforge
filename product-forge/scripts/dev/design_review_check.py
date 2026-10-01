"""Design/review intake guard (drift-guard, main tool).

Reads an incoming design/review/analysis document, searches the EXISTING code/architecture, and flags any
claim that violates, derails, is stale, or introduces a new path — so a decision is made BEFORE implementing.

Usage:
  python scripts/dev/design_review_check.py <doc.md> [--json]
  python scripts/dev/design_review_check.py <doc.md> --record --accept 1,2,3 [--scope product_forge]

Verdicts: aligned | violates | new-path | derails | stale.  Nothing is auto-accepted: non-`aligned` claims
require a human yes/no. `--record` writes the ACCEPTED claims as review-origin backlog items (with artifact/test
descriptors) so `intent_trace_check.py` can verify them later.
"""
import argparse
import json
import os
import re
import sys

os.environ.setdefault("API_ALLOW_ANON", "1")

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Anti-patterns derived from fixed decisions (AGENTS.md + governing updated plan). (regex, verdict, evidence)
ANTI_PATTERNS = [
    (r"route .*engineering .*intake|engineering .*through .*intake|use intake .*(task|worker|engineering)",
     "violates", "Intake is external ingestion only; engineering entry is the Task/Work API (engineering-flow.json)"),
    (r"second\s+(\w+\s+)?(engine|executor|backlog|store|database|validator|validation engine|git manager)",
     "violates", "one owner per concern; no duplicate engines/stores (config/store-registry.json)"),
    (r"dashboard\s*(api|server)|dashboard as authority|use .*dashboard .*authority",
     "violates", "legacy dashboard is frozen; not architecture authority (AGENTS.md)"),
    (r"opencode\s+(required|dependency|mandatory)|require .*opencode",
     "violates", "OpenCode is an adapter, never a dependency (updated plan 2.2)"),
    (r"git_manager", "stale", "core/git_manager.py was removed in ENG-3; use core/vcs.py"),
    (r"new top[- ]level director", "violates", "no new top-level directories (AGENTS.md placement rule)"),
    (r"direct(ly)? (write|mutat)\w* .*store", "violates", "no direct client-to-store mutation (single writer)"),
]
_VERB = re.compile(r"\b(use|add|create|replace|route|remove|require|make|integrate|implement|must|should|ensure|move|rename)\b", re.I)
_PATH = re.compile(r"[A-Za-z0-9_./-]+\.(?:py|json|md)")
_ROUTE = re.compile(r"/api/v1/[A-Za-z0-9_/{}\-]+")


def _registered_stores() -> set:
    try:
        with open(os.path.join(_ROOT, "config", "store-registry.json"), encoding="utf-8") as f:
            return set((json.load(f).get("stores") or {}).keys())
    except Exception:
        return set()


def _routes() -> set:
    try:
        from api.app import app
        return set(app.openapi().get("paths", {}).keys())
    except Exception:
        return set()


def extract_claims(text: str):
    claims = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line[0] in "#|>" or line.startswith("```"):
            continue
        m = re.match(r"^(?:[-*+]|\d+[.)])\s+(.*)$", line)
        body = (m.group(1) if m else line).strip()
        if len(body) < 12 or not _VERB.search(body):
            continue
        if body not in claims:
            claims.append(body)
    return claims[:60]


def _descriptors(claim: str):
    descs = []
    for r in _PATH.findall(claim):
        if r.endswith(".json"):
            descs.append("store:" + r.split("/")[-1])
        elif "test" in r.lower() or r.endswith("_test.py"):
            descs.append("test:" + r)
        else:
            descs.append("module:" + r)
    for rt in _ROUTE.findall(claim):
        descs.append("route:" + rt)
    return descs


def classify(claim: str, stores: set, routes: set):
    for pat, verdict, evidence in ANTI_PATTERNS:
        if re.search(pat, claim, re.I):
            return verdict, evidence
    found = False
    for r in _PATH.findall(claim):
        base = r.split("/")[-1]
        if r.endswith(".json") and base not in stores:
            return "violates", f"unregistered store {r} (register in config/store-registry.json)"
        if os.path.exists(os.path.join(_ROOT, r)) or base in stores:
            found = True
        elif r.endswith((".py", ".md")):
            return "new-path", f"referenced path not found: {r}"
    for rt in _ROUTE.findall(claim):
        if rt not in routes:
            return "new-path", f"route not registered: {rt}"
        found = True
    return ("aligned", "references existing components") if found else \
        ("new-path", "no existing component referenced (needs review)")


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Design/review intake guard")
    ap.add_argument("doc")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--record", action="store_true", help="write ACCEPTED claims as backlog items")
    ap.add_argument("--accept", default="", help="comma-separated claim numbers to accept (with --record)")
    ap.add_argument("--scope", default="product_forge")
    a = ap.parse_args(argv)

    try:
        with open(a.doc, encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except Exception as e:
        print(f"design-review: cannot read {a.doc}: {e}")
        return 1

    stores, routes = _registered_stores(), _routes()
    claims = extract_claims(text)
    rows = []
    for i, c in enumerate(claims, 1):
        v, ev = classify(c, stores, routes)
        rows.append({"n": i, "claim": c, "verdict": v, "evidence": ev, "descriptors": _descriptors(c)})

    if a.json:
        print(json.dumps(rows, indent=2))
    else:
        print(f"design-review: {a.doc}  ({len(rows)} claim(s))")
        for r in rows:
            print(f"{r['n']:>3}. [{r['verdict']:9}] {r['claim']}")
            print(f"       evidence: {r['evidence']}")
        needs = [r["n"] for r in rows if r["verdict"] != "aligned"]
        print("NEEDS DECISION:", needs or "none")

    if a.record:
        accept = {int(x) for x in re.split(r"[,\s]+", a.accept) if x.strip().isdigit()}
        if not accept:
            print("design-review: --record needs --accept <claim numbers>")
            return 1
        from core import backlog
        created = []
        for r in rows:
            if r["n"] not in accept:
                continue
            it = backlog.add_epic(a.scope, None, r["claim"][:120],
                                  body=f"{r['claim']}\n\nsource: {os.path.basename(a.doc)}#{r['n']}\n"
                                       f"verdict: {r['verdict']}\n{r['evidence']}",
                                  origin="review", source="review",
                                  external_id=f"{os.path.basename(a.doc)}::{r['n']}",
                                  links={"backend_capability": r["descriptors"]})
            created.append(it.get("id"))
        print("recorded:", ", ".join(created) or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
