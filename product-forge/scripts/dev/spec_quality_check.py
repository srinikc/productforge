"""Deterministic quality checks for functional/design specs."""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
for p in (str(ROOT),str(ROOT/"scripts"/"dev")): sys.path.insert(0,p)
from core import backlog
CFG=ROOT/"config"/"functional-spec.json"

def cfg(): return json.loads(CFG.read_text(encoding="utf-8-sig"))
def enforced(item,c):
    if str(item.get("id")) in (c.get("enforce_items") or []): return True
    return False
def _norm(x): return re.sub(r"\s+"," ",str(x or "")).strip().lower()
def problems(item):
    c=cfg()
    if not enforced(item,c): return []
    bad=[]
    acs=item.get("acceptance_criteria") or []
    spec=item.get("functional_spec") or {}
    frs=spec.get("requirements") or []
    if not acs: bad.append("acceptance_criteria missing")
    if not frs: bad.append("functional requirements missing")
    if len(acs)!=len(frs): bad.append(f"AC/FR count mismatch: AC={len(acs)} FR={len(frs)}")
    seen_ac={}
    for i,a in enumerate(acs,1):
        n=_norm(a)
        if n in seen_ac: bad.append(f"duplicate AC text: AC-{i} duplicates AC-{seen_ac[n]}")
        seen_ac[n]=i
        matches=[r for r in frs if str(r.get("source") or "")==f"AC-{i}"]
        if len(matches)!=1: bad.append(f"AC-{i} must map to exactly one FR (got {len(matches)})")

    rev=item.get("review") or {}
    rec=rev.get("reconciliation") or {}
    for k in ("prior_decisions","existing_path","assumptions","divergences"):
        if not rec.get(k): bad.append(f"reconciliation.{k} empty")
    impacts=rev.get("impact_review") or []
    claims=" ".join(str(r.get("claim") or "").lower() for r in impacts)
    for k in ("api","ac","language"):
        if k not in claims: bad.append(f"impact_review missing {k.upper()} CHECK")
    ae=spec.get("ac_evidence") or (item.get("design_pack") or {}).get("ac_evidence")
    if isinstance(ae,dict):
        for i in range(1,len(acs)+1):
            if f"AC-{i}" not in ae: bad.append(f"ac_evidence missing AC-{i}")
            elif not str((ae.get(f"AC-{i}") or {}).get("evidence") or "").strip(): bad.append(f"ac_evidence AC-{i} has no evidence")
    elif isinstance(ae,list):
        have={str(r.get("ac")) for r in ae if isinstance(r,dict) and r.get("evidence")}
        for i in range(1,len(acs)+1):
            if f"AC-{i}" not in have: bad.append(f"ac_evidence missing AC-{i}")
    else: bad.append("ac_evidence missing")
    return bad

def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument("--item"); ap.add_argument("--all",action="store_true"); a=ap.parse_args(argv)
    c=cfg(); bad=[]
    if a.all:
        for it in backlog.list_items("product_forge",None):
            bad += [f"{it.get('id')}: {x}" for x in problems(it)]
    elif a.item:
        it=backlog.get_epic("product_forge",None,a.item) or {}
        bad += [f"{a.item}: {x}" for x in problems(it)]
    else: print("spec-quality: --item or --all required",file=sys.stderr); return 2
    print("spec-quality: "+("OK" if not bad else "FAIL"))
    for x in bad: print("  - "+x)
    return 0 if not bad else 1
if __name__=="__main__": raise SystemExit(main())
