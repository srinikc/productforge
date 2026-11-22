"""Author-time pre-code Gate 1 guardrail (BI-PF-1449 / BI-PF-1466 / BI-PF-1469 / RCCA).

Blocks commits containing implementation code or tests on a feature branch until
Gate 1 (Human-In-The-Loop design approval) is recorded in the backlog.

Allowed without Gate 1:
  - Non-code files: backlog items (data/backlog/**), documentation (docs/**, *.md, *.txt),
    Gate 1.5 review files (engineering/reviews/**), audit trails (engineering/trails/**),
    issues (issues/**), and scratch/scratchpad files.
  - Baseline items (config/gate-baseline.json with active validity).
  - Protected branches (develop, main, master - handled by branch_guard.py).
  - Merge commits (MERGE_HEAD present).
  - Explicit audited bypass: PF_ALLOW_UNAPPROVED_CODE=1 or PF_ALLOW_UNGUARDED=1.

Exit 0 = allow, 1 = block.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "scripts" / "dev"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Ensure local EDP token default is present so local backlog reads never fail with 401
os.environ.setdefault("PF_EDP_TOKEN", "pf-edp-local-token-32-chars-long")

import architect_review as ar  # noqa: E402
import branch_item_check as bic  # noqa: E402
import gate_predicates as gp  # noqa: E402

PROTECTED = ("develop", "main", "master")

# File patterns permitted to be committed BEFORE Gate 1 approval.
# These represent design specs, backlog metadata, review artifacts, and documentation.
NON_CODE_GLOBS = [
    "data/backlog/**",
    "product-forge/data/backlog/**",
    "docs/**",
    "product-forge/docs/**",
    "engineering/reviews/**",
    "product-forge/engineering/reviews/**",
    "engineering/trails/**",
    "product-forge/engineering/trails/**",
    "engineering/changes.jsonl",
    "product-forge/engineering/changes.jsonl",
    "issues/**",
    "product-forge/issues/**",
    "scratch/**",
    "product-forge/scratch/**",
    "*.md",
    "**/*.md",
    "*.txt",
    "**/*.txt",
    "*.rst",
    "**/*.rst",
    ".gitignore",
]


def _git(*args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def current_branch() -> str:
    return _git("symbolic-ref", "--short", "-q", "HEAD")


def is_merge_in_progress() -> bool:
    return bool(_git("rev-parse", "-q", "--verify", "MERGE_HEAD"))


def staged_paths() -> list[str]:
    raw = _git("diff", "--cached", "--name-only")
    return [p.strip().replace("\\", "/") for p in raw.splitlines() if p.strip()]


def is_non_code_path(path: str) -> bool:
    norm = path.replace("\\", "/").strip()
    if norm.startswith("product-forge/"):
        norm_short = norm[len("product-forge/"):]
    else:
        norm_short = norm

    if norm.endswith((".md", ".txt", ".rst")) or norm_short.endswith((".md", ".txt", ".rst")):
        return True

    for g in NON_CODE_GLOBS:
        if fnmatch.fnmatch(norm, g) or fnmatch.fnmatch(norm_short, g):
            return True
    return False


def categorize_staged(paths: list[str]) -> tuple[list[str], list[str]]:
    non_code = []
    code = []
    for p in paths:
        if is_non_code_path(p):
            non_code.append(p)
        else:
            code.append(p)
    return non_code, code


def load_item_safe(item_id: str) -> dict:
    try:
        it = ar._get_item(item_id)
        if it and isinstance(it, dict):
            return it
    except Exception:
        pass
    for cand in (
        ROOT / "data" / "backlog" / "items" / f"{item_id}.json",
        ROOT / "product-forge" / "data" / "backlog" / "items" / f"{item_id}.json",
    ):
        if cand.is_file():
            try:
                return json.loads(cand.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def evaluate(
    branch: str,
    staged: list[str],
    merge: bool = False,
    env: dict | None = None,
    item_override: dict | None = None,
    view_override: dict | None = None,
) -> tuple[bool, str, list[str]]:
    """Evaluate pre-code boundary: (ok, reason, code_files)."""
    env = env if env is not None else dict(os.environ)

    # 1. Audited bypass
    if str(env.get("PF_ALLOW_UNAPPROVED_CODE") or env.get("PF_ALLOW_UNGUARDED") or "").strip().lower() in ("1", "true", "yes"):
        return True, "BYPASS_ENV", []

    # 2. Merge commits combine existing history
    if merge:
        return True, "MERGE_COMMIT", []

    # 3. Protected branches handled by branch_guard.py
    if branch in PROTECTED:
        return True, "PROTECTED_BRANCH", []

    # 4. Detached HEAD or branches without an item id (e.g. ad-hoc exploratory branches)
    item_id = bic.branch_id(branch)
    if not item_id:
        return True, "NO_ITEM_ID", []

    # 5. Check staged files
    if not staged:
        return True, "NO_STAGED_FILES", []

    _non_code, code_files = categorize_staged(staged)
    if not code_files:
        return True, "NON_CODE_ONLY", []

    # 6. Baseline exemption
    state = gp.baseline_state(item_id)
    if state == "ACTIVE":
        return True, "BASELINE_ACTIVE", []
    if state in {"EXPIRED", "UNKNOWN"}:
        return False, f"BASELINE_{state}", code_files

    # 7. Item resolution
    item = item_override if item_override is not None else load_item_safe(item_id)
    if not item or not isinstance(item, dict):
        return False, "ITEM_NOT_FOUND", code_files

    # 8. Gate 1.5 review evidence
    view = view_override if view_override is not None else ar.gate_view(item_id, "design")
    if view is None:
        return False, "NO_EVIDENCE", code_files
    if not view.get("parsed_ok", True):
        return False, "UNPARSABLE_REVIEW", code_files
    if view.get("blocking"):
        return False, "PENDING_FINDINGS", code_files

    # 9. Design SHA match
    sha = ar.design_sha(item)
    ev_sha = str(((view.get("review") or {}).get("sha")) or "")
    if ev_sha != sha:
        return False, "STALE_EVIDENCE", code_files

    # 10. Gate 1 approval decision
    ok, reason = gp.approval(item, 1, sha, view)
    if not ok:
        return False, reason, code_files

    return True, "OK", []


def format_block_message(item_id: str, branch: str, reason: str, code_files: list[str]) -> str:
    lines = [
        "=" * 78,
        "pre-code-gate: BLOCK - implementation code staged before Gate 1 HIL approval",
        "=" * 78,
        f"Branch: '{branch}' (item: {item_id})",
        f"Gate 1 status: {reason}",
        "",
        "Staged implementation files causing this block:",
    ]
    for cf in code_files[:15]:
        lines.append(f"  * {cf}")
    if len(code_files) > 15:
        lines.append(f"  * ... and {len(code_files) - 15} more file(s)")
    lines.extend([
        "",
        "Under Product Forge governance (BI-PF-1449 / BI-PF-1466 / BI-PF-1469 / RCCA),",
        "implementation code cannot be committed before completing Gate 0, Gate 1.5,",
        "and obtaining Gate 1 (Human-In-The-Loop) design approval in the backlog.",
        "This stops the momentum trap of writing code against an unapproved design.",
        "",
        "Required workflow to unlock code commits:",
        f"  1. Define item design & acceptance criteria in data/backlog/items/{item_id}.json",
        f"  2. Run Gate 0 check:",
        f"       python scripts/dev/gate0_check.py --item {item_id}",
        f"  3. Run Gate 1.5 Architect Review (design mode):",
        f"       python scripts/dev/architect_review.py run --item {item_id} --mode design --apply",
        f"  4. Disposition any BLOCKER or MAJOR findings:",
        f"       python scripts/dev/architect_review.py disposition --item {item_id} --mode design ...",
        f"  5. Obtain HIL approval and record Gate 1 decision:",
        f'       python scripts/dev/gate_decisions.py record --item {item_id} --gate 1 --decision APPROVE --by hil:<user> --reason "..."',
        "",
        "Audited bypass (for emergency or testing only): set PF_ALLOW_UNAPPROVED_CODE=1",
        "=" * 78,
    ])
    return "\n".join(lines)


def self_test() -> int:
    """Predicate unit test matrix for pre_code_gate."""
    view_good = {
        "parsed_ok": True,
        "blocking": [],
        "dispositions": {"sig:1": {"status": "ACTIONED"}},
        "review": {"sha": "sha_123", "at": "2026-01-01T00:00:00+00:00"},
    }
    digest = gp.findings_digest(view_good)
    item_approved = {
        "id": "BI-PF-9999",
        "decisions": [
            {
                "gate": 1,
                "decision": "APPROVE",
                "by": "hil:architect",
                "at": "2026-01-02T00:00:00+00:00",
                "findings_sha": "sha_123",
                "findings_digest": digest,
                "seq": 1,
            }
        ],
    }
    orig_design_sha = ar.design_sha
    ar.design_sha = lambda it: "sha_123"

    try:
        cases = [
            ("non_code_only", "feat/bi-pf-9999-task", ["docs/SPEC.md", "data/backlog/items/BI-PF-9999.json"],
             False, {}, item_approved, view_good, True, "NON_CODE_ONLY"),
            ("code_approved", "feat/bi-pf-9999-task", ["core/engine.py"],
             False, {}, item_approved, view_good, True, "OK"),
            ("code_no_decision", "feat/bi-pf-9999-task", ["core/engine.py"],
             False, {}, {"id": "BI-PF-9999", "decisions": []}, view_good, False, "NO_GATE_APPROVAL"),
            ("code_no_evidence", "feat/bi-pf-9999-task", ["core/engine.py"],
             False, {}, item_approved, None, False, "NO_EVIDENCE"),
            ("code_pending_findings", "feat/bi-pf-9999-task", ["core/engine.py"],
             False, {}, item_approved, dict(view_good, blocking=[{"severity": "BLOCKER"}]), False, "PENDING_FINDINGS"),
            ("code_stale_sha", "feat/bi-pf-9999-task", ["core/engine.py"],
             False, {}, item_approved, dict(view_good, review={"sha": "stale_sha"}), False, "STALE_EVIDENCE"),
            ("protected_branch", "develop", ["core/engine.py"],
             False, {}, item_approved, view_good, True, "PROTECTED_BRANCH"),
            ("merge_commit", "feat/bi-pf-9999-task", ["core/engine.py"],
             True, {}, item_approved, view_good, True, "MERGE_COMMIT"),
            ("bypass_env", "feat/bi-pf-9999-task", ["core/engine.py"],
             False, {"PF_ALLOW_UNAPPROVED_CODE": "1"}, {"id": "BI-PF-9999", "decisions": []}, None, True, "BYPASS_ENV"),
        ]

        failures = []
        for name, branch, staged, merge, env, it, v, want_ok, want_reason in cases:
            ok, reason, _ = evaluate(branch, staged, merge=merge, env=env, item_override=it, view_override=v)
            if ok != want_ok or reason != want_reason:
                failures.append(f"{name}: got ({ok}, {reason!r}), expected ({want_ok}, {want_reason!r})")

        if failures:
            for f in failures:
                print(f"pre_code_gate self-test: FAIL - {f}", file=sys.stderr)
            return 1

        print("pre_code_gate: self-test OK (9/9 scenarios passed)")
        return 0
    finally:
        ar.design_sha = orig_design_sha


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pre-commit pre-code Gate 1 guardrail")
    ap.add_argument("--self-test", action="store_true", help="Run self-tests")
    ap.add_argument("--item", help="Check specific item rather than resolving from branch")
    a = ap.parse_args(argv)

    if a.self_test:
        return self_test()

    branch = current_branch()
    staged = staged_paths()
    merge = is_merge_in_progress()

    if a.item:
        branch = f"feat/{a.item.lower()}-cli-check"

    item_id = a.item or bic.branch_id(branch)
    ok, reason, code_files = evaluate(branch, staged, merge=merge)

    if ok:
        if reason == "NON_CODE_ONLY":
            print("pre-code-gate: ALLOW - non-code files only (design/docs/reviews)")
        elif reason == "OK":
            print(f"pre-code-gate: OK - item {item_id} has Gate 1 HIL design approval")
        elif reason in ("PROTECTED_BRANCH", "MERGE_COMMIT", "NO_ITEM_ID", "NO_STAGED_FILES"):
            pass
        elif reason == "BYPASS_ENV":
            print("pre-code-gate: WARN - PF_ALLOW_UNAPPROVED_CODE set, bypassing Gate 1 check")
        elif reason == "BASELINE_ACTIVE":
            print(f"pre-code-gate: OK - item {item_id} active in gate-baseline.json")
        return 0

    print(format_block_message(item_id, branch, reason, code_files), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
