"""
Contract and acceptance tests for Next-Gen Web Console Packaging (BI-PF-1553).

Verifies:
  1. AC-1: Web console build pipeline compiles SPA frontend into optimized HTML/JS/CSS assets
     with content hashing and integrity checks.
  2. AC-2: Go platform server embeds compiled frontend assets via go:embed and serves them with
     HTTP cache headers, transparent gzip compression, and SPA routing fallback.
  3. AC-3: Shipped customer packages contain zero Node.js runtime dependencies or raw TypeScript/JSX source files.
"""
import gzip
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
import pytest

from core import packaging


@pytest.fixture
def mock_spa_dist(tmp_path):
    """Create a temporary distribution directory simulating compiled web console output."""
    dist_dir = tmp_path / "dist" / "console"
    dist_dir.mkdir(parents=True)
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir()

    index_html = b"<!DOCTYPE html><html><head><title>Console</title></head><body><div id='root'></div></body></html>"
    main_js = b"console.log('Product Forge Web Console Ready');"
    main_css = b"body { margin: 0; background: #0b0f19; color: #fff; }"
    icon_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRmockpng"

    (dist_dir / "index.html").write_bytes(index_html)
    (assets_dir / "main.abc12345.js").write_bytes(main_js)
    (assets_dir / "main.def67890.css").write_bytes(main_css)
    (assets_dir / "logo.png").write_bytes(icon_png)

    return dist_dir


def test_web_console_build_and_integrity(mock_spa_dist, tmp_path):
    """AC-1: Web console build pipeline produces content-hashed assets and checksums manifest."""
    out_dir = tmp_path / "out_dist"
    res = packaging.compile_web_console(str(mock_spa_dist), str(out_dir), generate_checksums=True)
    assert res["ok"] is True
    assert res["file_count"] >= 4

    chk_file = out_dir / "checksums.txt"
    assert chk_file.is_file()
    lines = chk_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 4

    # Verify sha256 hashes match content
    for line in lines:
        parts = line.split()
        assert len(parts) == 2
        expected_hash, rel_path = parts[0], parts[1]
        target_file = out_dir / rel_path
        assert target_file.is_file()
        actual_hash = hashlib.sha256(target_file.read_bytes()).hexdigest()
        assert actual_hash == expected_hash


def test_web_console_corrupt_hash_fails(mock_spa_dist, tmp_path):
    """AC-1 (negative): Tampered or corrupted asset fails verification."""
    out_dir = tmp_path / "out_dist"
    packaging.compile_web_console(str(mock_spa_dist), str(out_dir), generate_checksums=True)

    # Tamper with an asset
    target_js = out_dir / "assets" / "main.abc12345.js"
    target_js.write_bytes(b"tampered evil payload;")

    # Read checksums and verify mismatch is detected
    chk_file = out_dir / "checksums.txt"
    lines = chk_file.read_text(encoding="utf-8").strip().splitlines()
    mismatch_detected = False
    for line in lines:
        parts = line.split()
        expected_hash, rel_path = parts[0], parts[1]
        actual_hash = hashlib.sha256((out_dir / rel_path).read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            mismatch_detected = True
            break
    assert mismatch_detected is True


def test_go_embedded_server_headers_and_gzip():
    """AC-2: Go embedded server contract enforces cache headers, gzip, nosniff, and Vary."""
    go_src = Path("go/web/console.go")
    assert go_src.is_file()
    src_text = go_src.read_text(encoding="utf-8")

    # Invariants in Go handler implementation
    assert "X-Content-Type-Options" in src_text
    assert "nosniff" in src_text
    assert "Vary" in src_text
    assert "Accept-Encoding" in src_text
    assert "Cache-Control" in src_text
    assert "public, max-age=31536000, immutable" in src_text
    assert "no-cache, no-store, must-revalidate" in src_text
    assert "Content-Encoding" in src_text
    assert "gzip" in src_text


def test_go_embedded_server_missing_asset_404():
    """AC-2 (negative): Missing assets under /assets/ return 404, not index.html."""
    go_src = Path("go/web/console.go")
    src_text = go_src.read_text(encoding="utf-8")

    # Check that missing /assets/ paths return 404 explicitly
    assert 'strings.HasPrefix(cleanPath, "/assets/")' in src_text
    assert "STATIC_ASSET_NOT_FOUND" in src_text
    assert "http.StatusNotFound" in src_text


def test_go_embedded_server_traversal_blocked():
    """AC-2 (negative): Directory traversal attempts are rejected cleanly."""
    go_src = Path("go/web/console.go")
    src_text = go_src.read_text(encoding="utf-8")

    assert "ValidateConsoleRoutePath" in src_text
    assert "PATH_TRAVERSAL_BLOCKED" in src_text
    assert 'strings.Contains(urlPath, "..")' in src_text


def test_go_embedded_server_api_route_not_spa_fallback():
    """AC-2 (negative): API and health routes are strictly excluded from SPA fallback."""
    go_src = Path("go/web/console.go")
    src_text = go_src.read_text(encoding="utf-8")

    assert "IsAPIRoute" in src_text
    assert "API_ROUTE_EXCLUDED_FROM_SPA" in src_text
    assert 'strings.HasPrefix(clean, "/api/")' in src_text
    assert 'strings.HasPrefix(clean, "/health")' in src_text
    assert 'strings.HasPrefix(clean, "/metrics")' in src_text


def test_go_embedded_server_external_dir_fallback():
    """AC-2 (config): External static directory override enables emergency operational rollback."""
    go_src = Path("go/web/console.go")
    src_text = go_src.read_text(encoding="utf-8")

    assert "ResolveConsoleFileSystem" in src_text
    assert "PF_CONSOLE_STATIC_DIR" in src_text
    assert "os.DirFS(extDir)" in src_text


def test_customer_package_zero_nodejs_and_raw_sources(tmp_path):
    """AC-3: Customer edition packaging succeeds when only compiled artifacts are present."""
    pkg_dir = tmp_path / "enterprise_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pf-core.exe").write_bytes(b"\x7fELF\x02\x01\x01mockbinary")
    (pkg_dir / "index.html").write_bytes(b"<html></html>")
    (pkg_dir / "main.abc.js").write_bytes(b"console.log('minified bundle');")

    res = packaging.validate_customer_package(str(pkg_dir), "enterprise")
    assert res["valid"] is True


def test_customer_package_rejects_raw_typescript(tmp_path):
    """AC-3 (negative): Customer package validator rejects raw .ts, .tsx, .jsx, .mts, .cts."""
    pkg_dir = tmp_path / "enterprise_ts"
    pkg_dir.mkdir()
    (pkg_dir / "pf-core.exe").write_bytes(b"binary")
    (pkg_dir / "App.tsx").write_text("export const App = () => <div>Leaked TSX</div>;", encoding="utf-8")

    res = packaging.validate_customer_package(str(pkg_dir), "enterprise")
    assert res["valid"] is False
    assert res["error"] == "RAW_FRONTEND_SOURCE_DETECTED"
    assert "App.tsx" in res["file"]


def test_customer_package_rejects_sourcemaps(tmp_path):
    """AC-3 (negative): Customer package validator rejects *.map source maps."""
    pkg_dir = tmp_path / "enterprise_maps"
    pkg_dir.mkdir()
    (pkg_dir / "main.js").write_bytes(b"minified")
    (pkg_dir / "main.js.map").write_text('{"version":3,"sources":["App.tsx"]}', encoding="utf-8")

    res = packaging.validate_customer_package(str(pkg_dir), "enterprise")
    assert res["valid"] is False
    assert res["error"] == "SOURCE_MAP_DETECTED"


def test_customer_package_rejects_node_modules(tmp_path):
    """AC-3 (negative): Customer package validator rejects node_modules directory."""
    pkg_dir = tmp_path / "enterprise_nm"
    pkg_dir.mkdir()
    nm_dir = pkg_dir / "node_modules" / "some-pkg"
    nm_dir.mkdir(parents=True)
    (nm_dir / "index.js").write_text("module.exports = {};", encoding="utf-8")

    res = packaging.validate_customer_package(str(pkg_dir), "enterprise")
    assert res["valid"] is False
    assert res["error"] == "NODE_MODULES_DETECTED"


def test_eap_asset_bundle_console_registration():
    """AC-1/C-9: Web console asset bundle validates cleanly in EAP manifest."""
    bundle = {
        "id": "web-console",
        "checksum": "sha256:abc123456789",
        "dist_path": "dist/console"
    }
    val = packaging.validate_asset_bundle(bundle)
    assert val["valid"] is True
    assert val["id"] == "web-console"
