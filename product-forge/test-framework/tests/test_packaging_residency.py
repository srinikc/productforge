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
    assert "RESIDENCY_HOME_NOT_ALLOWED" in v["unmet"]


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
    assert "RESIDENCY_PROFILE_UNREADABLE" in v["unmet"]


def test_gate_report_is_non_fatal():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "dev" / "residency_gate.py"), "--report"],
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0
    assert "report_version" in (r.stdout or "")

def test_path_traversal_home_rejected():
    sec = json.loads((ROOT / "config" / "residency-manifest.json").read_text(encoding="utf-8"))
    sec["home_region"] = "../in"
    v = packaging.validate_residency(sec)
    assert v["valid"] is False
    assert "RESIDENCY_UNKNOWN_HOME" in v["unmet"]
