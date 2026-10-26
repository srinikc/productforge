"""EDP-12 residency manifest + build/deploy gate tests (BI-PF-1304)."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import packaging  # noqa: E402


def test_build_emits_in_template_and_validates():
    m = packaging.build("project", "_test_packaging_residency", edition="community")
    sec = m.get("residency") or {}
    assert sec.get("home_region") == "IN"
    assert sec.get("allowed_regions") == ["IN"]
    assert sec.get("backup", {}).get("frequency") == "daily"
    assert sec.get("validation", {}).get("valid") is True
    assert packaging.validate(m)["valid"] is True


def test_validate_rejects_missing_residency():
    m = packaging.build("project", "_test_packaging_residency", edition="community")
    m.pop("residency")
    v = packaging.validate(m)
    assert v["valid"] is False
    assert any("residency:RESIDENCY_MISSING_GROUP" in x for x in v["unmet"])


def test_profile_bounds_reject_region_widening():
    sec = json.loads((ROOT / "config" / "residency-manifest.json").read_text(encoding="utf-8"))
    sec["allowed_regions"] = ["IN", "US"]
    v = packaging.validate_residency(sec)
    assert v["valid"] is False
    assert "RESIDENCY_REGION_NOT_ALLOWED" in v["unmet"]


def test_invalid_backup_kms_retention():
    sec = json.loads((ROOT / "config" / "residency-manifest.json").read_text(encoding="utf-8"))
    sec["backup"]["encrypted"] = False
    sec["backup"]["frequency"] = "sometimes"
    sec["kms"]["rotation_days"] = 0
    sec["retention"]["days"] = 0
    errs = packaging.validate_residency(sec)["unmet"]
    for code in ("RESIDENCY_BACKUP_UNENCRYPTED", "RESIDENCY_UNKNOWN_FREQUENCY",
                 "RESIDENCY_KMS_ROTATION", "RESIDENCY_RETENTION"):
        assert code in errs


def test_unknown_home_fails_closed():
    sec = json.loads((ROOT / "config" / "residency-manifest.json").read_text(encoding="utf-8"))
    sec["home_region"] = "XX"
    v = packaging.validate_residency(sec)
    assert v["valid"] is False
    assert "RESIDENCY_UNKNOWN_HOME" in v["unmet"]


def test_gate_report_is_non_fatal(tmp_path):
    import os
    env = dict(os.environ, PF_RESIDENCY_EVENT=str(tmp_path / "residency_gate_scratch.json"),
               PF_RESIDENCY_JSONL=str(tmp_path / "residency_gate_scratch.jsonl"))
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "dev" / "residency_gate.py"), "--report"],
                       capture_output=True, text=True, timeout=180, env=env)
    assert r.returncode == 0
    assert "report_version" in (r.stdout or "")

def test_path_traversal_home_rejected():
    sec = json.loads((ROOT / "config" / "residency-manifest.json").read_text(encoding="utf-8"))
    sec["home_region"] = "../in"
    v = packaging.validate_residency(sec)
    assert v["valid"] is False
    assert "RESIDENCY_UNKNOWN_HOME" in v["unmet"]

def test_gate_block_and_warn_exit_codes(tmp_path):
    import os
    man = json.loads((ROOT / "config" / "residency-manifest.json").read_text(encoding="utf-8"))
    man["backup"]["regions"] = ["US"]
    path = tmp_path / "residency_manifest_scratch.json"
    path.write_text(json.dumps(man), encoding="utf-8")
    env = dict(os.environ, PF_RESIDENCY_EVENT=str(tmp_path / "residency_gate_scratch.json"),
               PF_RESIDENCY_JSONL=str(tmp_path / "residency_gate_scratch.jsonl"))
    cmd = [sys.executable, str(ROOT / "scripts" / "dev" / "residency_gate.py"),
           "--manifest", str(path), "--mode", "block"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
    assert r.returncode == 1, r.stdout + r.stderr
    cmd[cmd.index("block")] = "warn"
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
    assert r.returncode == 0 and "WARN" in r.stderr

def test_product_override_precedence(tmp_path, monkeypatch):
    monkeypatch.setattr(packaging, "PRODUCTS_DIR", tmp_path)
    d = tmp_path / "proj"
    d.mkdir()
    man = {"home_region": "IN"}
    (d / "residency-manifest.json").write_text(json.dumps(man), encoding="utf-8")
    assert packaging.residency_path("product_forge", "proj") == str(d / "residency-manifest.json")


def test_gate_invalid_manifest_fails_closed(tmp_path):
    import os
    tag = "invalid"
    path = tmp_path / f"residency_manifest_{tag}_{1}.json"
    path.write_text("{not json", encoding="utf-8")
    env = dict(os.environ, PF_RESIDENCY_EVENT=str(tmp_path / "residency_gate_scratch.json"),
               PF_RESIDENCY_JSONL=str(tmp_path / "residency_gate_scratch.jsonl"))
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "dev" / "residency_gate.py"),
                        "--manifest", str(path), "--mode", "block"], capture_output=True, text=True,
                       timeout=180, env=env)
    assert r.returncode != 0


def test_language_and_precheck_wiring():
    cfg = json.loads((ROOT / "config" / "language-rule.json").read_text(encoding="utf-8-sig"))
    assert "core/packaging.py" in ((cfg.get("edit_growth") or {}).get("allow") or [])
    assert "residency_gate.py" in (ROOT / "scripts" / "dev" / "precheck.py").read_text(encoding="utf-8")
