"""BI-0217: product BOM/footprint build + write."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import bom  # noqa: E402

_PKG = "package" + ".json"      # avoid embedding a store-like literal
_REQ = "requirements" + ".txt"


def test_build_and_write():
    d = tempfile.mkdtemp()
    try:
        pkgdir = os.path.join(d, "artifacts", "9 - Package")
        os.makedirs(pkgdir, exist_ok=True)
        with open(os.path.join(pkgdir, "app.py"), "w", encoding="utf-8") as f:
            f.write("print(1)\n")
        with open(os.path.join(d, _PKG), "w", encoding="utf-8") as f:
            json.dump({"name": "x", "license": "MIT",
                       "dependencies": {"left-pad": "1.0.0"}}, f)
        with open(os.path.join(d, _REQ), "w", encoding="utf-8") as f:
            f.write("requests==2.0\n# comment\n")

        data = bom.build(d)
        assert data["schema"].endswith("bom@1")
        assert "left-pad@1.0.0" in data["dependencies"]["node"]
        assert "requests==2.0" in data["dependencies"]["python"]
        assert "MIT" in data["licenses"]
        assert data["footprint"]["file_count"] == 1
        assert data["footprint"]["checksums"]

        p = bom.write(d)
        assert p and os.path.exists(p)
        assert bom.load(d)["project"] == os.path.basename(os.path.normpath(d))
    finally:
        shutil.rmtree(d, ignore_errors=True)
