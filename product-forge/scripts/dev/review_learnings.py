"""BI-PF-1449: turn Gate 1.5/2.5 findings into a learning loop.

Reads the committed review evidence (``engineering/reviews/*.json``) and reports:
  - findings per review + per severity (is review churn trending down?),
  - recurring finding signatures across reviews,
  - proposed CORRECTION-LEDGER rows for recurring findings that are NOT yet captured.

A finding is "captured" when its stable signature digest (``sig:<10-hex>``) appears in
``docs/CORRECTION-LEDGER.md``. ``--propose`` emits the ledger rows (each carries its digest), so adding
one silences ``--check`` and makes the rule durable + machine-traceable.

Run:
  python scripts/dev/review_learnings.py                 # human report
  python scripts/dev/review_learnings.py --check          # exit 1 if recurring findings are uncaptured
  python scripts/dev/review_learnings.py --propose        # emit CORRECTION-LEDGER rows
  python scripts/dev/review_learnings.py --json           # machine output
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVID = ROOT / "engineering" / "reviews"
LEARNINGS = ROOT / "engineering" / "learnings" / "review-findings.json"
LEDGER = ROOT / "docs" / "CORRECTION-LEDGER.md"
SEV = ("BLOCKER", "MAJOR", "MINOR", "NIT")
_SIG_RE = re.compile(r"sig:([0-9a-f]{10})")


def load_reviews(dir_path: Path | None = None) -> list[dict]:
    d = dir_path or EVID
    out: list[dict] = []
    bad = 0
    if not d.is_dir():
        return out
    for fp in sorted(d.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            bad += 1
            continue
        findings = data.get("findings")
        if not isinstance(findings, dict):
            continue
        out.append({"file": fp.name, "item": data.get("item"), "mode": data.get("mode"),
                    "sha": data.get("sha"), "mtime": fp.stat().st_mtime, "findings": findings})
    if bad:
        print(f"review-learnings: WARN {bad} unreadable review file(s) skipped", file=sys.stderr)
    return out


def signature(text: str) -> str:
    """Stable normalisation: lowercase, drop code spans/punctuation, collapse whitespace, first 14 words."""
    s = str(text or "").lower()
    s = re.sub(r"`[^`]*`", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return " ".join(s.split()[:14])


def digest(text: str) -> str:
    return hashlib.sha1(signature(text).encode("utf-8")).hexdigest()[:10]


def ledger_digests(path: Path | None = None) -> set[str]:
    p = path or LEDGER
    try:
        return set(_SIG_RE.findall(p.read_text(encoding="utf-8")))
    except Exception:
        return set()


def aggregate(reviews: list[dict]) -> dict:
    severity = Counter()
    sig: dict[str, dict] = {}
    per_review = []
    for r in reviews:
        n = 0
        for s in SEV:
            for t in (r.get("findings") or {}).get(s, []) or []:
                if str(t).strip().lower() in ("none", ""):
                    continue
                n += 1
                severity[s] += 1
                k = digest(t)
                rec = sig.setdefault(k, {"count": 0, "severity": s, "text": str(t), "items": set()})
                rec["count"] += 1
                rec["items"].add(str(r.get("item") or r.get("file") or "?"))
        per_review.append({"item": r.get("item"), "mode": r.get("mode"),
                           "mtime": r.get("mtime"), "findings": n})
    return {"reviews": len(reviews), "severity": dict(severity),
            "signatures": sig, "per_review": per_review}


def recurring(agg: dict, threshold: int) -> list[tuple[str, dict]]:
    return sorted(((k, v) for k, v in agg["signatures"].items() if v["count"] >= threshold),
                  key=lambda kv: (-kv[1]["count"], kv[0]))


def unresolved(agg: dict, ledger: set[str], threshold: int) -> list[tuple[str, dict]]:
    return [(k, v) for k, v in recurring(agg, threshold) if k not in ledger]


def _report(agg: dict, threshold: int) -> None:
    n = agg["reviews"] or 1
    total = sum(agg["severity"].values())
    print(f"review-learnings: {agg['reviews']} review(s), {total} finding(s) "
          f"({total / n:.1f}/review)")
    for s in SEV:
        print(f"  {s:8} {agg['severity'].get(s, 0):4}  ({agg['severity'].get(s, 0) / n:.1f}/review)")
    rec = recurring(agg, threshold)
    print(f"recurring signatures (>= {threshold} occurrences): {len(rec)}")
    for k, v in rec[:15]:
        items = ",".join(sorted(v["items"])[:3])
        print(f"  sig:{k}  x{v['count']:<3} [{v['severity']}] {v['text'][:90]}")
        print(f"      items: {items}")


def write_report(agg: dict, ledger: set[str], threshold: int, path: Path | None = None) -> Path:
    """Persist the machine-readable trend/recurrence report (durable learning home consumed by RAG).

    Deterministic (no timestamp) so re-running over unchanged evidence produces an identical file.
    """
    p = path or LEARNINGS
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = recurring(agg, threshold)
    payload = {
        "schema": "pf.review-learnings/1",
        "reviews": agg["reviews"],
        "severity": agg["severity"],
        "findings_per_review": round(sum(agg["severity"].values()) / (agg["reviews"] or 1), 2),
        "per_review": [{"item": r.get("item"), "mode": r.get("mode"), "findings": r.get("findings")}
                       for r in agg["per_review"]],
        "recurring": [{"sig": k, "count": v["count"], "severity": v["severity"], "text": v["text"],
                       "items": sorted(v["items"]), "captured": k in ledger} for k, v in rec],
        "uncaptured": len(unresolved(agg, ledger, threshold)),
    }
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


def _propose(agg: dict, ledger: set[str], threshold: int) -> int:
    todo = unresolved(agg, ledger, threshold)
    if not todo:
        print("review-learnings: no uncaptured recurring findings - ledger is up to date")
        return 0
    print("Proposed CORRECTION-LEDGER rows (add to docs/CORRECTION-LEDGER.md §6):")
    print("| id | correction (rule) | enforcement |")
    print("|---|---|---|")
    for k, v in todo:
        rule = v["text"].replace("|", "/").strip()[:180]
        enf = ("design pre-check checklist (config/architect-review.json) + gate1_check"
               if v["severity"] in ("BLOCKER", "MAJOR") else "design pre-check checklist")
        print(f"| CL-XXX | {rule} | {enf} <!-- sig:{k} --> |")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Review-findings learning loop (BI-PF-1449)")
    ap.add_argument("--threshold", type=int, default=2, help="occurrences to count as recurring (default 2)")
    ap.add_argument("--check", action="store_true", help="exit 1 when recurring findings are uncaptured")
    ap.add_argument("--propose", action="store_true", help="print CORRECTION-LEDGER rows to add")
    ap.add_argument("--write", action="store_true", help="persist the durable report (engineering/learnings/review-findings.json)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    agg = aggregate(load_reviews())
    ledger = ledger_digests()
    todo = unresolved(agg, ledger, max(1, a.threshold))
    if a.write:
        print(f"review-learnings: wrote {write_report(agg, ledger, max(1, a.threshold))}")
    if a.json:
        print(json.dumps({
            "reviews": agg["reviews"], "severity": agg["severity"],
            "recurring": [{"sig": k, "count": v["count"], "severity": v["severity"],
                           "text": v["text"], "items": sorted(v["items"]), "captured": k in ledger}
                          for k, v in recurring(agg, max(1, a.threshold))],
            "uncaptured": len(todo),
        }, indent=2))
        return 1 if (a.check and todo) else 0
    if a.propose:
        return _propose(agg, ledger, max(1, a.threshold))
    _report(agg, max(1, a.threshold))
    if a.check and todo:
        print(f"review-learnings: {len(todo)} recurring finding(s) NOT captured in the correction ledger")
        print("  run: python scripts/dev/review_learnings.py --propose")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
