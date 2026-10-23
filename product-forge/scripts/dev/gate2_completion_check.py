"""BI-PF-1469: hard Gate 2 at the backlog `-> completed/closed/done` transition.

Completion requires:
  * the latest committed Gate 2.5 (diff) evidence for this item, parseable with zero PENDING findings;
  * a Gate 2 decision (gate=2, APPROVE/APPROVE_WITH_ATTENTION, by hil:<actor>) bound to that evidence sha and
    to the current findings digest.

Docs/config-only changes (nothing outside the size-gate skip globs) have no Gate 2.5 evidence; their Gate 2
decision must use findings_sha="docs-only". Expired/unknown baseline entries hard-fail. --report is a dry-run.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "scripts" / "dev"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import architect_review as ar  # noqa: E402
from core import gate_predicates as gp  # noqa: E402

_MARK = "/data/backlog/items/"
DONE = {"completed", "closed", "done"}


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True)
    return (r.stdout or "").strip()


def _repo_root() -> str:
    return _git("rev-parse", "--show-toplevel") or str(ROOT)


def _load(rel_repo: str) -> dict:
    try:
        return json.loads(Path(_repo_root(), rel_repo).read_text(encoding="utf-8"))
    except Exception:
        return {}


def transitions(base: str = "") -> list[str]:
    base = base or _git("merge-base", "develop", "HEAD") or "origin/develop"
    out = []
    for rel in _git("diff", "--name-only", f"{base}..HEAD").splitlines():
        rel = rel.replace("\\", "/")
        if _MARK not in rel or not rel.endswith(".json") or rel.endswith("open.json") or rel.endswith("closed.json"):
            continue
        cur = _load(rel)
        if str(cur.get("status") or "").lower() not in DONE:
            continue
        prev_raw = _git("show", f"{base}:{rel}")
        try:
            prev = json.loads(prev_raw) if prev_raw else {}
        except Exception:
            prev = {}
        if str(prev.get("status") or "").lower() not in DONE:
            out.append(str(cur.get("id") or Path(rel).stem))
    return sorted(set(out))


def _docs_only() -> bool:
    cfg = ar._config()
    skip = (cfg.get("size_gate") or {}).get("skip_globs") or ["docs/**", "**/*.md", "config/**"]
    files = ar.changed_files()
    return not any(not any(fnmatch.fnmatch(f, g) for g in skip) for f in files)


def check(ids: list[str]) -> list[tuple[str, str]]:
    problems: list[tuple[str, str]] = []
    docs_only = _docs_only()
    for iid in ids:
        state = gp.baseline_state(iid)
        if state == "ACTIVE":
            print(f"gate2: ALLOW item={iid} reason=BASELINE")
            continue
        if state in {"EXPIRED", "UNKNOWN"}:
            problems.append((iid, f"BASELINE_{state}"))
            continue
        view = ar.gate_view(iid, "diff")
        if view is None and not docs_only:
            problems.append((iid, "NO_DIFF_EVIDENCE"))
            continue
        if view is not None and not view.get("parsed_ok", True):
            problems.append((iid, "UNPARSABLE"))
            continue
        if view is not None and view.get("blocking"):
            problems.append((iid, "PENDING_DIFF_FINDINGS"))
            continue
        sha = ((view or {}).get("review") or {}).get("sha") if view else "docs-only"
        item = ar._get_item(iid)
        ok, reason = gp.gate2_ready(item, str(sha or ""), view, allow_missing_view=view is None)
        if not ok:
            problems.append((iid, reason))
        else:
            print(f"gate2: ALLOW item={iid} reason=OK sha={sha}")
    return problems


def _self_test() -> int:
    """Predicate matrix: allow, no decision, pending findings, stale evidence, expired baseline."""
    import tempfile
    base = {"parsed_ok": True, "blocking": [], "dispositions": {"sig:a": {"status": "ACTIONED"}},
            "review": {"sha": "abc"}}
    digest = gp.findings_digest(base)
    item = {"decisions": [{"gate": 2, "decision": "APPROVE", "by": "hil:test",
                           "findings_sha": "abc", "findings_digest": digest}]}
    cases = [
        ("allow", item, "abc", base, True, "OK"),
        ("no-decision", {"decisions": []}, "abc", base, False, "NO_GATE_APPROVAL"),
        ("pending", item, "abc", dict(base, blocking=["x"]), False, "PENDING_FINDINGS"),
        ("stale", item, "zzz", base, False, "STALE_APPROVAL"),
    ]
    bad = []
    for name, it, sha, view, want_ok, want_reason in cases:
        ok, reason = gp.gate2_ready(it, sha, view, allow_missing_view=False)
        if ok != want_ok or reason != want_reason:
            bad.append(f"{name}: got {ok}/{reason}, want {want_ok}/{want_reason}")
    with tempfile.TemporaryDirectory() as td:
        from pathlib import Path as _P
        tmp = _P(td) / "gate_baseline.tmp"
        tmp.write_text('{"items": {"BI-X": {"until": "2000-01-01", "reason": "x", "owner_item": "BI-Y"}}}', encoding="utf-8")
        old = gp.BASELINE
        gp.BASELINE = tmp
        try:
            if gp.baseline_state("BI-X") != "EXPIRED":
                bad.append("expired baseline was not detected")
            if gp.baseline_state("BI-UNKNOWN") != "NONE":
                bad.append("unknown baseline entry was not NONE")
        finally:
            gp.BASELINE = old
    if bad:
        for b in bad:
            print("gate2 self-test: FAIL - " + b)
        return 1
    print("gate2: self-test OK (allow, no-decision, pending, stale, baseline expiry)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gate 2 completion enforcement (BI-PF-1469)")
    ap.add_argument("--report", action="store_true", help="dry-run: report only, exit 0")
    ap.add_argument("--self-test", action="store_true", help="run the predicate negative matrix")
    ap.add_argument("--base", default="", help="git base (default merge-base develop)")
    a = ap.parse_args(argv)
    if a.self_test and _self_test() != 0:
        return 1
    for b in gp.baseline_problems():
        print(f"gate2: BASELINE_CONFIG {b}")
    ids = transitions(a.base)
    problems = check(ids)
    if a.report:
        print(f"gate2: REPORT {len(ids)} completion(s), {len(problems)} would fail")
        for iid, why in problems:
            print(f"gate2: DENY item={iid} reason={why}")
        return 0
    if problems:
        print(f"gate2-completion: FAIL ({len(problems)} item(s) lack Gate 2.5/Gate 2)")
        for iid, why in problems:
            print(f"gate2: DENY item={iid} reason={why}")
        print("   fix: run Gate 2.5 (architect_review run), disposition, then record a gate=2 decision")
        return 1
    print(f"gate2-completion: OK ({len(ids)} completion(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
