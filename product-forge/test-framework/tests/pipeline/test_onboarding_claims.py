"""BI-PF-1205 (C3): onboarding templates must not assert unheld compliance certifications."""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")


def test_no_hardcoded_cert_or_absolute_privacy_claims():
    src = (ROOT / "core" / "customer_onboarding.py").read_text(encoding="utf-8")
    assert "SOC 2 Type II" not in src
    assert "we never share your data" not in src.lower()
