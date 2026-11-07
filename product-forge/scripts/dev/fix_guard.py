"""Fix-impact guard: every latest BLOCKER/MAJOR needs a fix-impact row."""
from __future__ import annotations
import argparse, json, sys
from datetime import date, datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
for p in (str(ROOT),str(ROOT/'scripts'/'dev')): sys.path.insert(0,p)
from core import backlog
from review_sig import digest
CFG=ROOT/'config'/'fix-impact.json'

def cfg(): return json.loads(CFG.read_text(encoding='utf-8-sig'))
def exp(v):
    s=str(v or '')
    if not s: return None
    try: return datetime.fromisoformat(s).date()
    except ValueError: return date.fromisoformat(s)
def enforced(item,c):
    if str(item.get('id')) in (c.get('enforce_items') or []): return True
    a,b=exp(item.get('created_at')),exp(c.get('enforce_from'))
    return bool(a and b and a>=b)
def latest_review(iid):
    files=sorted((ROOT/'engineering'/'reviews').glob(f'{iid}-*.json'),key=lambda p:p.stat().st_mtime)
    for p in reversed(files):
        try: d=json.loads(p.read_text(encoding='utf-8'))
        except Exception: continue
        if d.get('mode')=='diff': return d
    return {}
def problems(item,c=None):
    c=c or cfg()
    if not enforced(item,c): return []
    rows=item.get('fix_impact')
    if not isinstance(rows,list) or not rows: return ['fix_impact missing']
    bad=[]
    rev=latest_review(str(item.get('id')))
    req=[x for sev in ('BLOCKER','MAJOR') for x in ((rev.get('findings') or {}).get(sev) or []) if '[OUT_OF_SCOPE]' not in str(x)]
    bysig={str(r.get('sig')):r for r in rows if isinstance(r,dict)}
    for text in req:
        sig='sig:'+digest(text)
        r=bysig.get(sig)
        if not r:
            bad.append(f'fix_impact missing {sig}')
            continue
        if str(r.get('status','')).upper()!='ACTIONED': bad.append(f'{sig} status not ACTIONED')
    for i,r in enumerate(rows,1):
        if not isinstance(r,dict): bad.append(f'fix_impact[{i}] not object'); continue
        for k in c.get('required_fields') or []:
            if not r.get(k): bad.append(f'fix_impact[{i}].{k} missing')
        if str(r.get('origin_class')) not in (c.get('origin_classes') or []):
            bad.append(f'fix_impact[{i}].origin_class invalid')
        for f in r.get('files') or []:
            p=Path(f); p=p if p.is_absolute() else ROOT/p
            if not p.exists(): bad.append(f'fix_impact[{i}] file not found: {f}')
        for e in ([r.get('evidence')] if isinstance(r.get('evidence'),str) else (r.get('evidence') or [])):
            p=Path(str(e)); p=p if p.is_absolute() else ROOT/p
            if not p.exists(): bad.append(f'fix_impact[{i}] evidence not found: {e}')
        arts=set(r.get('artifacts_updated') or [])
        for a in c.get('required_artifacts') or []:
            if a not in arts: bad.append(f'fix_impact[{i}].artifacts_updated missing {a}')
    return bad
def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument('--item'); ap.add_argument('--all',action='store_true'); a=ap.parse_args(argv)
    c=cfg(); bad=[]
    if a.all:
        for it in backlog.list_items('product_forge',None):
            bad += [f"{it.get('id')}: {x}" for x in problems(it,c)]
    elif a.item:
        it=backlog.get_epic('product_forge',None,a.item) or {}
        bad += [f"{a.item}: {x}" for x in problems(it,c)]
    else:
        print('fix-guard: --item or --all required',file=sys.stderr); return 2
    print('fix-guard: '+('OK' if not bad else 'FAIL'))
    for x in bad: print('  - '+x)
    return 0 if not bad else 1
if __name__=='__main__': raise SystemExit(main())
