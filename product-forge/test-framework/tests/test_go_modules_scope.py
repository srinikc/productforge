"""go-modules scoping path normalization (BI-PF-1474)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import go_modules_check as g  # noqa: E402


def test_porcelain_status_is_normalized():
    diff = "product-forge/go/s3store/s3store.go\n"
    status = " M product-forge/go/objstore/objstore.go\nR  go/a.go -> go/b.go\n?? product-forge/go/new/x.go\n"
    paths = g._normalize_paths(diff, status)
    assert "go/s3store/s3store.go" in paths
    assert "go/objstore/objstore.go" in paths
    assert "go/b.go" in paths
    assert "go/new/x.go" in paths
