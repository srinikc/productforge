"""BI-PF-1168 (E7): architecture/contract gate - contracts, migration, trust boundaries, data model, license."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import spec_review as sr  # noqa: E402


def _arch_recs(fs):
    return [f for f in fs if f["category"] == "architecture"]


def test_architecture_missing_areas_flagged():
    thin = "Architecture: components and services, performance and security. " + "detail " * 60
    fs, _ = sr._review_one("docs/architecture.md", "architect", thin, 0)
    recs = _arch_recs(fs)
    assert recs
    joined = " ".join(r["recommendation"] for r in recs)
    assert "trust boundaries" in joined and "migration" in joined


def test_complete_architecture_passes():
    good = ("Architecture: components + services, performance, security, reliability. "
            "Interfaces/contracts (OpenAPI schema). Migration strategy (backward-compatible versioning). "
            "Trust boundaries + threat model (authz/authentication perimeter). Data model entities/schema. "
            "Dependency license + bundle_allowed decision. " + "detail " * 60)
    fs, _ = sr._review_one("docs/architecture.md", "architect", good, 0)
    assert not _arch_recs(fs)
