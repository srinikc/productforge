"""Gate 2.5 ENFORCEMENT (deterministic, offline; BI-PF-1428).

The Gate 1.5/2.5 second-model architect review must have HAPPENED (evidence exists) for any change that
touches code / schema / security - this gate proves it without calling a model (so it is safe in precheck/CI).

Rule:
  - Compute the current diff vs origin/develop (same exclusions as scripts/dev/architect_review.py: committed
    evidence + the baseline file do not change the sha).
  - Skip when the change set is docs/config-only (the size gate in config/architect-review.json).
  - Otherwise REQUIRE a matching evidence file engineering/reviews/*-<sha>.json (or the sha is grandfathered
    in config/architect-review-baseline.json - bootstrap only).
Fail-closed. Fix: python scripts/dev/architect_review.py run --item <ID>  (then commit the evidence).

Run: python scripts/dev/architect_review_check.py   (wired into precheck fast -> blocks PR/merge).
"""
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import architect_review as ar  # noqa: E402

EVID = ROOT / "engineering" / "reviews"
BASELINE = ROOT / "config" / "architect-review-baseline.json"


def _cfg() -> dict:
    try:
        return json.loads((ROOT / "config" / "architect-review.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _is_ancestor(base: str, head: str) -> bool:
    try:
        r = subprocess.run(["git", "merge-base", "--is-ancestor", base, head], cwd=str(ROOT),
                           capture_output=True, text=True)
        return r.returncode == 0
    except Exception:
        return False


def valid_base(base: str, head: str, prior_heads: set, merge_base: str) -> bool:
    """A delta base must be a real ancestor and either merge-base or a prior reviewed head."""
    if not base or not head or base == head:
        return False
    if base != merge_base and base not in prior_heads:
        return False
    return _is_ancestor(base, head)


def _baseline_shas() -> set:
    try:
        return set(json.loads(BASELINE.read_text(encoding="utf-8")).get("shas") or [])
    except Exception:
        return set()


def is_applicable(files: list, skip_globs: list) -> bool:
    """Any file NOT matching a skip glob makes the change review-required (defaults: docs/config-only)."""
    for f in files:
        if not any(fnmatch.fnmatch(f, g) for g in skip_globs):
            return True
    return False


def main() -> int:
    cfg = _cfg()
    skip = (cfg.get("size_gate") or {}).get("skip_globs") or ["docs/**", "**/*.md", "config/**"]
    try:
        files = ar.changed_files()
        if not is_applicable(files, skip):
            print(f"architect-review: OK (skip - no code/schema/security change; {len(files)} file(s))")
            return 0
        sha = ar.diff_sha()
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
        print(f"architect-review: FAIL - cannot compute the change set (fail-closed): {e}")
        return 1

    if sha in _baseline_shas():
        print(f"architect-review: OK (baseline sha {sha})")
        return 0
    hits = list(EVID.glob(f"*-{sha}.json")) if EVID.is_dir() else []
    if not hits and EVID.is_dir():
        head = ar._git_text(["rev-parse", "HEAD"]).strip()
        mb = ar._merge_base()
        evs = []
        for p in EVID.glob("*.json"):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            evs.append((p, d))
        evs.sort(key=lambda pd: str(pd[1].get("at") or ""))
        by_item = {}
        for p, d in evs:
            iid = str(d.get("item") or "")
            if iid:
                by_item.setdefault(iid, []).append(d)
        for path, d in reversed(evs):
            if d.get("mode") != "diff" or str(d.get("head_sha") or "") != head:
                continue
            base = str(d.get("base_sha") or "")
            if not base or base == head:
                continue
            iid = str(d.get("item") or "")
            if not iid:
                continue
            prior_heads = {str(x.get("head_sha") or "") for x in by_item.get(iid, [])
                           if x.get("mode") == "diff" and x.get("head_sha") and str(x.get("head_sha")) != head}
            if valid_base(base, head, prior_heads, mb):
                reviewed_head = str(d.get("head_sha") or "")
                if reviewed_head and reviewed_head != head:
                    since = ar._git_text(["diff", "--name-only", f"{reviewed_head}..HEAD", "--", ".", *ar.EXCLUDE])
                    if since.strip():
                        continue
                if path.is_file():
                    hits = [path]
                    break
    if hits:
        print(f"architect-review: OK (evidence {hits[0].name})")
        return 0

    print(f"architect-review: FAIL - no Gate 2.5 evidence for this change (sha={sha})")
    print("   fix: python scripts/dev/architect_review.py run --item <ID>   (commit engineering/reviews/<ID>-<sha>.json)")
    print("   see: docs/REVIEW-GATES-LIFECYCLE.md (Gate 2.5)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
