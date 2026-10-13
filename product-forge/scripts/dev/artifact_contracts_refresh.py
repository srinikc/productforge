"""Artifact Contract Registry refresh (source-driven, never silent).

For each contract that declares ``refresh.mode == "check"`` and a fetchable source URL,
compare the upstream content hash to the pinned ``integrity.sha256``:

  --check                 report current | stale | unreachable | manual (no network write)
  --propose <artifact>    fetch upstream, write a PROPOSAL (snapshot + diff) - does NOT apply
  --apply <artifact> [--bump patch|minor|major]
                          apply the reviewed proposal: bump format_version, update
                          integrity (sha256/retrieved_at), append provenance.jsonl

Offline-safe: any network error is reported, never fatal. Paywalled sources
(``refresh.mode == "manual"``) are skipped (outline maintained by hand).

Run: python scripts/dev/artifact_contracts_refresh.py --check
"""
import argparse
import datetime
import hashlib
import json
import os
import sys
import urllib.request

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import contracts  # noqa: E402

_DIR = os.path.join(_ROOT, "config", "artifact-contracts")
_INDEX = os.path.join(_DIR, "index.json")
_PROV = os.path.join(_DIR, "provenance.jsonl")
_PROPOSALS = os.path.join(_DIR, "proposals")


def _fetch(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "product-forge-contract-refresh"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        return r.read()


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _save_index(reg: dict) -> None:
    with open(_INDEX, encoding="utf-8-sig") as f:
        doc = json.load(f)
    doc["contracts"] = reg
    tmp = _INDEX + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, _INDEX)


def _prov(entry: dict) -> None:
    os.makedirs(_DIR, exist_ok=True)
    with open(_PROV, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _bump(v: str, part: str) -> str:
    try:
        a, b, c = (int(x) for x in str(v or "0.0.0").split(".")[:3])
    except Exception:
        a, b, c = 0, 0, 0
    if part == "major":
        a, b, c = a + 1, 0, 0
    elif part == "minor":
        b, c = b + 1, 0
    else:
        c += 1
    return f"{a}.{b}.{c}"


def _source_url(c: dict) -> str:
    src = c.get("source") or {}
    return src.get("raw_template_url") or src.get("repo_url") or src.get("canonical_url") or ""


def do_check(reg: dict) -> int:
    rows = []
    for aid, c in reg.items():
        mode = (c.get("refresh") or {}).get("mode", "manual")
        if mode == "manual":
            rows.append((aid, "manual", ""))
            continue
        url = _source_url(c)
        if not url:
            rows.append((aid, "no-source", ""))
            continue
        try:
            body = _fetch(url)
        except Exception as e:  # noqa: BLE001
            rows.append((aid, "unreachable", type(e).__name__))
            continue
        pinned = str((c.get("integrity") or {}).get("sha256") or "")
        now = _sha(body)
        rows.append((aid, "current" if (pinned and pinned == now) else "stale", now[:12]))
    stale = [r for r in rows if r[1] == "stale"]
    for aid, st, extra in rows:
        print(f"  {st:11} {aid} {extra}")
    print(f"artifact-contracts-refresh: {len(stale)} stale / {len(rows)} contracts")
    return 0


def do_propose(reg: dict, aid: str) -> int:
    c = reg.get(aid)
    if not c:
        print(f"unknown contract {aid}")
        return 1
    url = _source_url(c)
    if not url:
        print(f"{aid}: no source url to fetch")
        return 1
    try:
        body = _fetch(url)
    except Exception as e:  # noqa: BLE001
        print(f"{aid}: fetch failed: {type(e).__name__}: {e}")
        return 1
    os.makedirs(_PROPOSALS, exist_ok=True)
    stamp = datetime.date.today().isoformat()
    snap = os.path.join(_PROPOSALS, f"{aid}.{stamp}.snapshot")
    with open(snap, "wb") as f:
        f.write(body)
    prop = {"artifact_id": aid, "at": stamp, "source_url": url, "sha256": _sha(body),
            "snapshot": os.path.relpath(snap, _ROOT),
            "pinned_sha256": (c.get("integrity") or {}).get("sha256", ""),
            "proposed_format_version": _bump(c.get("format_version", "1.0.0"), "minor"),
            "note": "REVIEW then: --apply %s --bump minor" % aid}
    with open(os.path.join(_PROPOSALS, f"{aid}.{stamp}.proposal.json"), "w", encoding="utf-8") as f:
        json.dump(prop, f, indent=2, ensure_ascii=False)
    print(json.dumps(prop, indent=2, ensure_ascii=False))
    return 0


def do_apply(reg: dict, aid: str, part: str) -> int:
    c = reg.get(aid)
    if not c:
        print(f"unknown contract {aid}")
        return 1
    url = _source_url(c)
    try:
        body = _fetch(url)
    except Exception as e:  # noqa: BLE001
        print(f"{aid}: fetch failed: {type(e).__name__}: {e}")
        return 1
    old = c.get("format_version", "1.0.0")
    new = _bump(old, part)
    c.setdefault("integrity", {})["sha256"] = _sha(body)
    c["retrieved_at"] = datetime.date.today().isoformat()
    c["format_version"] = new
    c.setdefault("provenance", []).append(
        {"at": c["retrieved_at"], "from": old, "to": new, "action": "refresh", "by": "cli"})
    _save_index(reg)
    _prov({"artifact_id": aid, "at": c["retrieved_at"], "from": old, "to": new,
           "sha256": c["integrity"]["sha256"], "source_url": url})
    print(f"{aid}: applied {old} -> {new}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Artifact contract registry refresh")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--propose", default="")
    ap.add_argument("--apply", default="")
    ap.add_argument("--bump", default="minor", choices=["patch", "minor", "major"])
    a = ap.parse_args(argv)
    reg = contracts.load_registry()
    if a.apply:
        return do_apply(reg, a.apply, a.bump)
    if a.propose:
        return do_propose(reg, a.propose)
    return do_check(reg)


if __name__ == "__main__":
    raise SystemExit(main())
