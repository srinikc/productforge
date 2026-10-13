"""Artifact Contract Registry gate.

Asserts (via the Go engine, core/go_host.py -> go/pfcore/artifact_contracts.go):
  * EVERY agent (agents/*.agent.json) and EVERY stage (pipeline-definition.json) is
    covered in config/artifact-contracts/agents.json -> contract id(s) or ["none"];
  * every referenced contract id exists in config/artifact-contracts/index.json;
  * every contract carries the required metadata (sections, source, license,
    format_version) so it can be refreshed/versioned.

A NEW (or dynamically created) agent/stage with no coverage entry FAILS this gate, so
new pipelines cannot ship without declaring the artifacts they produce.

Run: ``python scripts/dev/artifact_contracts_check.py`` (hermetic; no network).
"""
import glob
import json
import os
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import contracts  # noqa: E402

FAILS = []


def _all_agents() -> list:
    ids = []
    for f in sorted(glob.glob(os.path.join(_ROOT, "agents", "*.agent.json"))):
        try:
            with open(f, encoding="utf-8-sig") as fh:
                d = json.load(fh)
            if d.get("id"):
                ids.append(str(d["id"]))
        except Exception:
            pass
    return ids


def _all_stages() -> list:
    try:
        with open(os.path.join(_ROOT, "pipeline-definition.json"), encoding="utf-8-sig") as f:
            return list((json.load(f).get("stages") or {}).keys())
    except Exception:
        return []


def main() -> int:
    agents = _all_agents()
    stages = _all_stages()
    reg = contracts.load_registry()

    if not reg:
        print("artifact-contracts: FAIL (registry empty or Go host unavailable)")
        return 1

    cov = contracts.coverage(agents, stages)
    for a in (cov.get("missing_agents") or []):
        FAILS.append(f"agent '{a}' has NO contract mapping (add to agents.json)")
    for s in (cov.get("missing_stages") or []):
        FAILS.append(f"stage '{s}' has NO contract mapping (add to agents.json)")
    for b in (cov.get("bad_contracts") or []):
        FAILS.append(f"contract issue: {b}")

    # agent registry coverage (BI-PF-1349): every agent has a spec + valid outputs.
    acov = contracts.agent_coverage(agents)
    for a in (acov.get("missing_agents") or []):
        FAILS.append(f"agent '{a}' has NO agent-registry spec (config/agent-registry/index.json)")
    for b in (acov.get("bad_specs") or []):
        FAILS.append(f"agent spec issue: {b}")

    # resolve smoke (must not raise)
    r = contracts.resolve(agent="design", stage="1", kind="text")
    if not r.get("contracts"):
        FAILS.append("resolve(design/1) returned no contracts")

    if FAILS:
        print("artifact-contracts: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print(f"artifact-contracts: OK ({len(reg)} contracts; {len(agents)} agents, "
          f"{len(stages)} stages covered; engine=go)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
