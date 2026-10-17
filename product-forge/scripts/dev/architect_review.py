"""Gate 2.5 / Gate 1.5 - second-model Architect review helper (BI-PF-1427, ADR/process: docs/REVIEW-GATES-LIFECYCLE.md).

Model-agnostic by design: the reviewer is usually a DIFFERENT model (default Mimo v2.6/flash) in a FRESH
context. This tool:
  * emit  : builds the architect-review prompt from the item + AC + (design | git diff) + standards.
  * ingest: parses a review (BLOCKER/MAJOR/MINOR/NIT), writes evidence engineering/reviews/<item>-<sha>.json,
            and (--apply) appends the summary to the item's context via the API.

Why not call the model here: the catalog is stale (mimo-v2.6 absent) and model calls must not sit inside
precheck. Emitting the prompt lets ANY reviewer model produce the review; ingest captures it as evidence.

Usage:
  python scripts/dev/architect_review.py emit   --item BI-PF-XXXX [--mode design|diff]
  python scripts/dev/architect_review.py ingest --item BI-PF-XXXX --file review.md [--apply]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVID = ROOT / "engineering" / "reviews"
CONFIG = ROOT / "config" / "architect-review.json"
API = os.environ.get("PF_API_URL", "http://127.0.0.1:8010/api/v1")
SEVERITIES = ("BLOCKER", "MAJOR", "MINOR", "NIT")


def _config() -> dict:
    """Provider/model-agnostic config (config/architect-review.json). Any model id is valid."""
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}

PROMPT = """You are a Principal Enterprise System Architect performing an independent review.

Review the {target}. Judge from an ENTERPRISE, LONG-TERM perspective: integrity, adaptability, scalability,
security, observability, maintainability, reuse (no duplication), and "are we doing the right thing".
Do NOT rewrite code; produce findings.

Item: {item}
Acceptance Criteria:
{ac}

Standards: follow AGENTS.md, docs/ENGINEERING_OPERATING_STANDARD.md, docs/ARCHITECTURE-DECISIONS.md
(language rule: new shipped logic -> Go; edits to shipped Python allowed; tooling Python OK).

{body}

Output format (exact headings, bullet findings):
### BLOCKER
- <objectively verifiable blocker, e.g. data loss, secret, RLS bypass, missing migration/test, language-rule violation>
### MAJOR
- <design/robustness issue>
### MINOR
- <minor>
### NIT
- <nit>
### SUMMARY
- <2-5 lines: overall verdict + top risks>
"""


def _get_item(item: str) -> dict:
    tok = os.environ.get("PF_API_TOKEN", "") or (ROOT / "data" / "local" / "dev-api-token").read_text().strip()
    req = urllib.request.Request(f"{API.rstrip('/')}/backlog/items/{item}", method="GET")
    req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8")).get("data") or {}


def _git_diff() -> str:
    try:
        return subprocess.run(["git", "diff", "--no-color", "origin/develop..."], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return ""


def _design_body(item: dict) -> str:
    keys = ("objective", "approach", "in_scope", "out_of_scope", "acceptance_criteria",
            "affected_components", "affected_files", "risks", "rollback")
    return "Design / Gate-1 context:\n" + "\n".join(f"- {k}: {item.get(k)}" for k in keys if item.get(k))


def parse_review(text: str) -> dict:
    out = {s: [] for s in SEVERITIES}
    out["SUMMARY"] = []
    cur = None
    for line in text.splitlines():
        m = re.match(r"^\s*#{2,4}\s*(BLOCKER|MAJOR|MINOR|NIT|SUMMARY)\s*$", line, re.IGNORECASE)
        if m:
            cur = m.group(1).upper()
            continue
        if cur and re.match(r"^\s*[-*]\s+", line):
            out[cur].append(re.sub(r"^\s*[-*]\s+", "", line).strip())
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Gate 2.5 / 1.5 architect review (BI-PF-1427).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    default_model = os.environ.get("PF_ARCHITECT_REVIEW_MODEL") or _config().get("model", "mimo-v2.6-flash")
    e = sub.add_parser("emit")
    e.add_argument("--item", required=True)
    e.add_argument("--mode", choices=["design", "diff"], default="diff")
    e.add_argument("--model", default=default_model, help="reviewer model label (configurable)")
    ing = sub.add_parser("ingest")
    ing.add_argument("--item", required=True)
    ing.add_argument("--file", required=True)
    ing.add_argument("--apply", action="store_true")
    ing.add_argument("--model", default=default_model, help="reviewer model label recorded in evidence")
    a = ap.parse_args(argv)

    item = _get_item(a.item)
    if a.cmd == "emit":
        ac = "\n".join(f"- {c}" for c in (item.get("acceptance_criteria") or [])) or "- (none)"
        body = _design_body(item) if a.mode == "design" else "Diff:\n```diff\n" + _git_diff()[:60000] + "\n```"
        print(f"Reviewer model: {a.model}\n")
        print(PROMPT.format(target=("design" if a.mode == "design" else "implementation diff"),
                            item=a.item, ac=ac, body=body))
        return 0

    text = Path(a.file).read_text(encoding="utf-8")
    findings = parse_review(text)
    sha = hashlib.sha256(_git_diff().encode("utf-8")).hexdigest()[:12]
    EVID.mkdir(parents=True, exist_ok=True)
    out = EVID / f"{a.item}-{sha}.json"
    out.write_text(json.dumps({"item": a.item, "sha": sha, "model": a.model,
                               "findings": findings}, indent=2), encoding="utf-8")
    counts = {s: len(findings[s]) for s in SEVERITIES}
    print(f"review captured: {out} {counts}")
    blockers = findings["BLOCKER"]
    if a.apply:
        summary = "; ".join(blockers) if blockers else "no blockers"
        tok = os.environ.get("PF_API_TOKEN", "") or (ROOT / "data" / "local" / "dev-api-token").read_text().strip()
        body = json.dumps({"verification": [f"Gate2.5 architect review ({counts}): {summary}"]}).encode("utf-8")
        req = urllib.request.Request(f"{API.rstrip('/')}/backlog/items/{a.item}/context", data=body, method="POST")
        req.add_header("Authorization", f"Bearer {tok}")
        req.add_header("Content-Type", "application/json")
        req.add_header("X-Roles", "operator")
        urllib.request.urlopen(req, timeout=15).read()
        print("summary appended to item context")
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
