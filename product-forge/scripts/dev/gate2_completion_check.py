"""BI-PF-1469/1470: hard Gate 2 at the backlog `-> completed/closed/done` transition.

Completion requires:
  * the latest committed Gate 2.5 (diff) evidence for this item, parseable with zero PENDING findings;
  * a Gate 2 decision (gate=2, APPROVE/APPROVE_WITH_ATTENTION, by hil:<actor>) bound to that evidence sha and
    to the current findings digest.

Data-only completion PRs (nothing outside the size-gate skip globs) have no Gate 2.5 evidence of their own;
they are validated against the delivery evidence named by the newest Gate 2 decision (deterministic across
checkouts). Expired/unknown baseline entries hard-fail. --report is a dry-run.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "scripts" / "dev"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import architect_review as ar  # noqa: E402
import gate_predicates as gp  # noqa: E402

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
    return gp.is_docs_only(ar.changed_files(), skip)


def check(ids: list[str]) -> list[tuple[str, str]]:
    problems: list[tuple[str, str]] = []
    docs_only = _docs_only()
    for iid in ids:
        item = ar._get_item(iid)
        # Validate against the delivery evidence named by the newest Gate 2 decision; this works for
        # data-only and mixed PRs alike (the decision is bound to the reviewed delivery diff).
        view = None
        for d in reversed((item.get("decisions") or [])):
            try:
                g = int(d.get("gate") or 0)
            except Exception:
                g = 0
            sha_d = str(d.get("findings_sha") or "")
            if g == 2 and sha_d and sha_d != "docs-only":
                view = ar.gate_view_sha(iid, "diff", sha_d)
                if view is not None:
                    break
        if view is None:
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
        # Evidence freshness for the CURRENT code change is enforced by architect_review_check; a
        # completion may legitimately ride in a PR that also touches other files.
        ok, reason = gp.gate2_ready(item, str(sha or ""), view, allow_missing_view=view is None)
        if not ok:
            problems.append((iid, reason))
        else:
            print(f"gate2: ALLOW item={iid} reason=OK sha={sha}")
    return problems


def _self_test() -> int:
    base = {"parsed_ok": True, "blocking": [], "dispositions": {"sig:a": {"status": "ACTIONED"}},
            "review": {"sha": "abc", "at": "2026-01-01T00:00:00+00:00"}}
    digest = gp.findings_digest(base)
    item = {"decisions": [{"gate": 2, "decision": "APPROVE", "by": "hil:test",
                           "at": "2026-01-02T00:00:00+00:00", "seq": 1,
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
    if gp.force_allowed({"PF_GATE_FORCE": "1"}) is not True:
        bad.append("force should be allowed with PF_GATE_FORCE=1 only")
    if gp.force_allowed({}) or gp.force_allowed({"PF_CI": "1", "PF_GATE_FORCE": "1"}):
        bad.append("force must be refused without PF_GATE_FORCE or with PF_CI present")
    if bad:
        for b in bad:
            print("gate2 self-test: FAIL - " + b)
        return 1
    print("gate2: self-test OK (allow, no-decision, pending, stale, force)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gate 2 completion enforcement (BI-PF-1469/1470)")
    ap.add_argument("--report", action="store_true", help="dry-run: report only, exit 0")
    ap.add_argument("--self-test", action="store_true", help="run the predicate negative matrix")
    ap.add_argument("--base", default="", help="git base (default merge-base develop)")
    a = ap.parse_args(argv)
    if a.self_test and _self_test() != 0:
        return 1
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
        print("   fix: run Gate 2.5, disposition findings, record a gate=2 decision")
        return 1
    print(f"gate2-completion: OK ({len(ids)} completion(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
