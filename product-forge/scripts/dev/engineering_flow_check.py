"""ENG-0 gate: the engineering architecture is defined AND stitched/wired.

Validates ``config/engineering-flow.json`` against reality:
  * ``core.engineering_flow.validate()``  - structure + every non-planned owner file exists.
  * every non-planned step's ``api`` route is registered on the canonical app (OpenAPI).
      -> an architecture that names an owner/route that does not exist cannot pass.

Run: ``python scripts/dev/engineering_flow_check.py`` (wired into precheck). Exit 1 on any failure.
"""
import os
import sys

os.environ.setdefault("API_ALLOW_ANON", "1")

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

FAILS = []


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def main() -> int:
    from core import engineering_flow
    res = engineering_flow.validate()
    for e in res.get("errors", []):
        FAILS.append(e)

    # entry-path contract: engineering flow starts at the direct entry and never routes via Intake
    eng = engineering_flow.flow()
    _check(bool(eng) and str(eng[0].get("id")) == "task_contract",
           "engineering flow must start at the direct entry 'task_contract'")
    _check(all(str(s.get("owner")) != "core/intake.py" for s in eng),
           "engineering flow must not contain an intake-owned step")

    from api.app import app
    paths = set(app.openapi().get("paths", {}).keys())
    for s in engineering_flow.flow() + engineering_flow.external_ingestion():
        if str(s.get("status")) == "planned":
            continue
        api = str(s.get("api") or "")
        if api:
            _check(api in paths, f"{s.get('id')}: api route not wired: {api}")

    if FAILS:
        print("engineering-flow: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print(f"engineering-flow: OK ({res.get('engineering', 0)} engineering steps, "
          f"{res.get('external_ingestion', 0)} ingestion steps, {res.get('planned', 0)} planned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
