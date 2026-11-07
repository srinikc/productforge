"""Require PF_BACKLOG_DB_SCOPES to match active backlog scopes."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from core import backlog

def main():
    allowed=backlog._backlog_db_scopes()
    active={"product_forge"}
    active |= {p.name for p in (ROOT/"products").iterdir() if (p/"data"/"backlog"/"items").is_dir()}
    unknown=sorted(allowed-active)
    unlisted=sorted(active-allowed)
    if unknown or unlisted:
        print(f"backlog-scope: FAIL unknown={unknown} unlisted={unlisted}")
        return 1
    print(f"backlog-scope: OK ({len(allowed)} scope(s))")
    return 0
if __name__=="__main__": raise SystemExit(main())
