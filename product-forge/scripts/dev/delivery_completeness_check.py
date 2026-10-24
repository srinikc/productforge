"""Evidence-based delivery completeness (BI-PF-1409).

Why: EDP-02 was closed as "complete" while store classification/mapping was missing - closure proved
artifact EXISTENCE, not completeness, and the AC merely restated the objective.

Enforced on every `-> completed` transition in the committed diff:
  * acceptance criteria and verification entries must be specific (no title/objective echo, no
    "Objective achieved:", no "Not specified."/empty), at least one of each;
  * items whose title/AC mentions RCCA must carry an rcca block (root_cause, corrective, preventive,
    fixed_where) and every path cited in fixed_where must exist.

Audit (report-only, bounded): completed items still carrying placeholder DoD are counted and compared with
config/delivery-completeness-baseline.json (owner + expiry + reason). An expired/unknown baseline fails.
Escape hatch: PF_ALLOW_PLACEHOLDER_DOD=1 downgrades transition failures to warnings (audited in output).

Output is a JSON report on stdout plus structured JSON event lines on stderr; --report exits 0; --self-test
runs the negative matrix.
"""
from __future__ import annotations

import argparse
import functools
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ITEMS = ROOT / "data" / "backlog" / "items"
BASELINE = ROOT / "config" / "delivery-completeness-baseline.json"
DONE = {"completed", "closed", "done"}
GENERIC = {"not specified.", "none", "tbd", "n/a", "-"}
MIN_FIELD = 15
MAX_BASELINE = 200


def _norm(s) -> str:
    return unicodedata.normalize("NFKC", str(s or "")).strip().casefold()


def placeholder(s, item: dict) -> bool:
    n = _norm(s)
    if not n or n in GENERIC:
        return True
    return (n == _norm(item.get("title")) or n == _norm(item.get("objective"))
            or n.startswith("objective achieved:") or n.startswith("objective achieved "))


def generic(item: dict) -> bool:
    acs = item.get("acceptance_criteria") or []
    ver = item.get("verification") or []
    return all(placeholder(a, item) for a in acs) or all(placeholder(v, item) for v in ver)


def _exists(path: str) -> bool:
    p = path.strip().strip("`")
    if not p:
        return False
    full = ROOT / p
    return full.exists() or bool(list(ROOT.glob(p)))


def rcca_problems(item: dict) -> list[str]:
    block = item.get("rcca") or {}
    bad = [f"rcca.{k} missing/short" for k in ("root_cause", "corrective", "preventive", "fixed_where")
           if len(str(block.get(k) or "").strip()) < MIN_FIELD]
    cited = [x for x in re.split(r"[;,]", str(block.get("fixed_where") or "")) if x.strip()]
    if block.get("fixed_where") and not any(_exists(x) for x in cited):
        bad.append("rcca.fixed_where cites no existing path")
    return bad


def transition_problems(item: dict) -> list[str]:
    bad: list[str] = []
    acs = item.get("acceptance_criteria") or []
    ver = item.get("verification") or []
    if not [a for a in acs if not placeholder(a, item)]:
        bad.append("no specific acceptance criterion")
    if not [v for v in ver if not placeholder(v, item)]:
        bad.append("no specific verification entry")
    blob = " ".join([str(item.get("title") or "")] + [str(a) for a in acs]).casefold()
    if "rcca" in blob:
        bad += rcca_problems(item)
    return bad


def _git(*args: str, allow_fail: bool = False) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as e:
        raise RuntimeError(f"delivery-completeness: git {' '.join(args)} failed: {e}") from e
    if r.returncode != 0 and not allow_fail:
        raise RuntimeError(f"delivery-completeness: git {' '.join(args)} failed (rc={r.returncode}): "
                           f"{(r.stderr or '').strip()}")
    return (r.stdout or "").strip()


@functools.lru_cache(maxsize=1)
def _repo_root() -> str:
    """Git top-level (the workspace root is an ancestor of product-forge in this layout)."""
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as e:
        raise RuntimeError(f"delivery-completeness: git rev-parse failed: {e}") from e
    out = (r.stdout or "").strip()
    if r.returncode != 0 or not out:
        raise RuntimeError(f"delivery-completeness: not in a git repo (rev-parse rc={r.returncode})")
    return out


def _load(rel_repo: str) -> dict | None:
    """Read a changed item from the git repo root, not from product-forge/ROOT.

    Returns None only for a path absent from the tree (deleted in the diff). A path escaping the repo root,
    an unreadable file, malformed JSON or a non-object item fails closed with the path in the error.
    """
    root = Path(_repo_root()).resolve()
    p = (root / rel_repo).resolve()
    try:
        p.relative_to(root)
    except ValueError as e:
        raise RuntimeError(f"delivery-completeness: changed item escapes the repo root: {rel_repo}") from e
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(f"delivery-completeness: cannot read changed item {rel_repo}: {e}") from e
    if not isinstance(data, dict):
        raise RuntimeError(f"delivery-completeness: changed item is not a JSON object: {rel_repo}")
    return data


def transitions(base: str = "") -> list[dict]:
    base = base or _git("merge-base", "develop", "HEAD", allow_fail=True) or "origin/develop"
    out = []
    skipped: list[str] = []
    for rel in _git("diff", "--name-only", f"{base}..HEAD").splitlines():
        rel = rel.replace("\\", "/")
        if "/data/backlog/items/" not in rel or not rel.endswith(".json"):
            continue
        cur = _load(rel)
        if cur is None:
            skipped.append(rel)
            continue
        if str(cur.get("status") or "").lower() not in DONE:
            continue
        prev_raw = _git("show", f"{base}:{rel}", allow_fail=True)
        try:
            prev = json.loads(prev_raw) if prev_raw else {}
        except Exception:
            prev = {}
        if str(prev.get("status") or "").lower() not in DONE:
            out.append(cur)
    if skipped:
        print(json.dumps({"event": "delivery-completeness-skip", "count": len(skipped),
                          "paths": sorted(skipped)}), file=sys.stderr)
    return out


def load_baseline() -> tuple[list[str], list[str]]:
    if not BASELINE.is_file():
        return [], []
    try:
        d = json.loads(BASELINE.read_text(encoding="utf-8"))
    except Exception as e:
        return [], [f"baseline unreadable: {e}"]
    bad = []
    for k in ("owner_item", "reason", "until"):
        if not str(d.get(k) or "").strip():
            bad.append(f"baseline missing {k}")
    try:
        until = date.fromisoformat(str(d.get("until")))
        if datetime.now(timezone.utc).date() > until:
            bad.append("baseline expired")
    except Exception:
        bad.append("baseline until is not an ISO date")
    items = [str(x) for x in (d.get("items") or [])]
    if len(items) > MAX_BASELINE:
        bad.append(f"baseline has {len(items)} entries (max {MAX_BASELINE})")
    return items, bad


def audit() -> tuple[list[str], list[str]]:
    baseline, bad = load_baseline()
    remaining = []
    for f in sorted(ITEMS.glob("*.json")):
        try:
            it = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(it.get("status") or "").lower() not in DONE:
            continue
        if generic(it) and str(it.get("id")) not in baseline:
            remaining.append(str(it.get("id")))
    return remaining, bad


def _emit(problems: list[str], warnings: list[str], ids: list[str]) -> int:
    payload = {"ok": not problems, "checked": ids, "problems": problems, "warnings": warnings}
    print(json.dumps(payload))
    return 0 if not problems else 1


def _self_test() -> int:
    good = {"title": "T", "objective": "O", "acceptance_criteria": ["Concrete AC that is long enough to be real"],
            "verification": ["Verified by an independent test run with evidence"]}
    ph = {"title": "T", "objective": "O", "acceptance_criteria": ["Objective achieved: O"], "verification": ["O"]}
    rcca = {"title": "RCCA thing", "acceptance_criteria": ["Concrete AC that is long enough here"],
            "verification": ["Concrete verification done"], "rcca": {"root_cause": "x" * 20, "corrective": "y" * 20,
            "preventive": "z" * 20, "fixed_where": "scripts/dev/delivery_completeness_check.py"}}
    bad = []
    if transition_problems(good):
        bad.append("good item rejected")
    if not transition_problems(ph):
        bad.append("placeholder item accepted")
    if rcca_problems(rcca):
        bad.append("valid RCCA rejected")
    if not rcca_problems(dict(rcca, rcca={"root_cause": "short"})):
        bad.append("invalid RCCA accepted")
    if bad:
        for b in bad:
            print("self-test: FAIL - " + b)
        return 1
    print("delivery-completeness: self-test OK (4 scenarios)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Delivery completeness gate (BI-PF-1409)")
    ap.add_argument("--report", action="store_true", help="dry-run: report only, exit 0")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--base", default="")
    a = ap.parse_args(argv)
    if a.self_test and _self_test() != 0:
        return 1
    problems: list[str] = []
    warnings: list[str] = []
    ids: list[str] = []
    for it in transitions(a.base):
        iid = str(it.get("id"))
        ids.append(iid)
        for p in transition_problems(it):
            (warnings if os.environ.get("PF_ALLOW_PLACEHOLDER_DOD") == "1" else problems).append(f"{iid}: {p}")
    remaining, base_bad = audit()
    problems += [f"baseline: {b}" for b in base_bad]
    if remaining:
        warnings.append(f"{len(remaining)} completed item(s) still carry placeholder DoD (baseline/audit)")
    if a.report:
        print(f"delivery-completeness: REPORT {len(ids)} completion(s), {len(problems)} problem(s), "
              f"{len(remaining)} legacy placeholder(s)")
        return 0
    code = _emit(problems, warnings, ids)
    if code:
        print(f"delivery-completeness: FAIL ({len(problems)} problem(s))")
    else:
        print(f"delivery-completeness: OK ({len(ids)} completion(s); {len(remaining)} legacy placeholders)")
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
