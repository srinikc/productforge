"""Single AC verification policy (BI-PF-1484)."""
from __future__ import annotations


def problems(item: dict) -> list[str]:
    acs = item.get("ac_verification") or []
    criteria = item.get("acceptance_criteria") or []
    out = []
    if not acs:
        out.append("no ac_verification recorded")
    if criteria and len(acs) < len(criteria):
        out.append(f"only {len(acs)} of {len(criteria)} ACs recorded")
    for a in acs:
        if str(a.get("result") or "").upper() != "PASS":
            out.append(f"AC not PASS: {a.get('ac')}")
    return out
