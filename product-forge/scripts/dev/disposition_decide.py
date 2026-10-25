"""Record a HIL DISPOSITION_APPROVAL for ACCEPTED/DEFERRED (BI-PF-1484)."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core import backlog  # noqa: E402
import disposition_policy as dp  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", required=True)
    ap.add_argument("--mode", choices=("design", "diff"), required=True)
    ap.add_argument("--by", required=True)
    ap.add_argument("--sigs", nargs="+", required=True)
    ap.add_argument("--note", required=True)
    ap.add_argument("--hil-confirmed", action="store_true", required=True)
    a = ap.parse_args()
    if not a.by.startswith("hil:"):
        print("disposition-decide: by must be hil:<actor>", file=sys.stderr)
        return 2
    it = backlog.get_epic("product_forge", None, a.item) or {}
    rows = (it.get("review_dispositions") or {}).get(a.mode) or {}
    bad = [s for s in a.sigs if str((rows.get(s) or {}).get("status") or "").upper() not in ("ACCEPTED", "DEFERRED")]
    if bad:
        print(f"disposition-decide: not ACCEPTED/DEFERRED: {bad}", file=sys.stderr)
        return 2
    dec = list(it.get("decisions") or [])
    dec.append({"at": datetime.now(timezone.utc).isoformat(), "by": a.by, "decision": "DISPOSITION_APPROVAL",
                "hil_confirmed": True, "scope": "disposition_approval", "mode": a.mode,
                "sigs": a.sigs, "note": a.note})
    backlog.update("product_forge", None, a.item, decisions=dec)
    print(f"disposition-decide: approved {len(a.sigs)} {a.mode} disposition(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
