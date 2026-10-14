"""Fail-closed monotonicity guard: a change must NEVER regress the backlog.

A work ITEM is append-mostly state: its ``revision`` and ``updated_at`` must not go
BACKWARD, and ``links.delivery`` / ``epic`` must not be dropped. A stale durable-state
checkpoint once overwrote newer items (revision/updated_at went backward, delivery/epic
lost, history lines deleted) - see the state-sync clobber RCCA. This gate compares the
CHANGED item files against the integration base and FAILS on any regression, so such a
merge/commit cannot land.

Diff-scoped (only files changed vs ``--base``), so pre-existing develop debt is ignored.
Fails closed on a detected regression; skips (exit 0) when the base ref is unavailable
(e.g. a shallow clone without the integration branch).

Run: ``python scripts/dev/backlog_monotonic_check.py [--base origin/develop]``
"""
import argparse
import json
import os
import subprocess
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_REPO = str(_ROOT)
_ITEMS_REL = "product-forge/data/backlog/items"


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", _REPO, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def _resolve_base(explicit: str) -> str:
    for ref in [explicit, "origin/develop", "develop", "HEAD~1"]:
        if ref and _git("rev-parse", "--verify", "-q", ref + "^{commit}").strip():
            return ref
    return ""


def _base_item(base: str, rel: str):
    txt = _git("show", f"{base}:{rel}")
    try:
        return json.loads(txt)
    except Exception:
        return None


def _work_item(rel: str):
    try:
        with open(os.path.join(_REPO, rel), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _problems(base: str) -> list:
    changed = _git("diff", "--name-only", base, "--", _ITEMS_REL).splitlines()
    out = []
    for rel in changed:
        rel = rel.strip()
        if not rel.endswith(".json"):
            continue
        b = _base_item(base, rel)
        w = _work_item(rel)
        iid = os.path.basename(rel)[:-5]
        if b is None:
            continue  # new item -> fine
        if w is None:
            out.append(f"{iid}: item deleted")
            continue
        br, wr = int(b.get("revision") or 0), int(w.get("revision") or 0)
        if wr < br:
            out.append(f"{iid}: revision regressed {br} -> {wr}")
        if str(w.get("updated_at") or "") < str(b.get("updated_at") or ""):
            out.append(f"{iid}: updated_at regressed {b.get('updated_at')} -> {w.get('updated_at')}")
        if (b.get("links") or {}).get("delivery") and not (w.get("links") or {}).get("delivery"):
            out.append(f"{iid}: delivery provenance dropped")
        if str(b.get("epic") or "").strip() and not str(w.get("epic") or "").strip():
            out.append(f"{iid}: epic link dropped (was {b.get('epic')})")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Backlog monotonicity guard (no regression vs base)")
    ap.add_argument("--base", default=os.environ.get("PF_MONOTONIC_BASE", "origin/develop"))
    a = ap.parse_args(argv)
    base = _resolve_base(a.base)
    if not base:
        print("backlog-monotonic: SKIP (no base ref available)")
        return 0
    probs = _problems(base)
    if probs:
        print(f"backlog-monotonic: FAIL ({len(probs)} regression(s) vs {base})")
        for p in probs[:25]:
            print("   -", p)
        return 1
    print(f"backlog-monotonic: OK (no item regressed vs {base})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
