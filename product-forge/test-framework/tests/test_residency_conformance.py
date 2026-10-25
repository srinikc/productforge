"""Cross-language residency conformance (BI-PF-1304 AC5)."""
import copy
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core import packaging  # noqa: E402

FIX = ROOT / "test-framework" / "tests" / "fixtures" / "residency_conformance.json"


def test_python_and_go_reach_the_same_verdict(tmp_path):
    data = json.loads(FIX.read_text(encoding="utf-8-sig"))
    for case in data["cases"]:
        man = copy.deepcopy(data["base"])
        man.update(copy.deepcopy(case.get("patch") or {}))
        p = tmp_path / f"{case['name']}.json"
        p.write_text(json.dumps(man), encoding="utf-8")
        py = packaging.validate_residency(man)
        assert py["valid"] is case["valid"], (case["name"], py)
        r = subprocess.run(["go", "run", "./cmd/pfresidency", "--manifest", str(p),
                            "--profiles", str(ROOT / "config" / "residency-profiles"),
                            "--mode", "block", "--report"],
                           cwd=str(ROOT / "go" / "residencymanifest"),
                           capture_output=True, text=True, timeout=120)
        go = json.loads((r.stdout or "{}").strip().splitlines()[-1]) if r.stdout.strip() else {}
        assert bool(go.get("ok")) is case["valid"], (case["name"], r.returncode, r.stdout, r.stderr)
        assert r.returncode in (0, 1), (case["name"], r.returncode, r.stderr)
