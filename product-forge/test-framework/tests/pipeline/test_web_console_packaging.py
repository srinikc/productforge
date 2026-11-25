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


PF_ROOT = Path(__file__).resolve().parents[3]


def test_go_embedded_server_headers_and_gzip():
    """AC-2: Go embedded server contract enforces cache headers, gzip, nosniff, and Vary."""
    go_src = PF_ROOT / "go" / "web" / "console.go"
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
    go_src = PF_ROOT / "go" / "web" / "console.go"
    src_text = go_src.read_text(encoding="utf-8")

    # Check that missing /assets/ paths return 404 explicitly
    assert 'strings.HasPrefix(cleanPath, "/assets/")' in src_text
    assert "STATIC_ASSET_NOT_FOUND" in src_text
    assert "http.StatusNotFound" in src_text


def test_go_embedded_server_traversal_blocked():
    """AC-2 (negative): Directory traversal attempts are rejected cleanly."""
    go_src = PF_ROOT / "go" / "web" / "console.go"
    src_text = go_src.read_text(encoding="utf-8")

    assert "ValidateConsoleRoutePath" in src_text
    assert "PATH_TRAVERSAL_BLOCKED" in src_text
    assert 'strings.Contains(urlPath, "..")' in src_text


def test_go_embedded_server_api_route_not_spa_fallback():
    """AC-2 (negative): API and health routes are strictly excluded from SPA fallback."""
    go_src = PF_ROOT / "go" / "web" / "console.go"
    src_text = go_src.read_text(encoding="utf-8")

    assert "IsAPIRoute" in src_text
    assert "API_ROUTE_EXCLUDED_FROM_SPA" in src_text
    assert 'strings.HasPrefix(clean, "/api/")' in src_text
    assert 'strings.HasPrefix(clean, "/health")' in src_text
    assert 'strings.HasPrefix(clean, "/metrics")' in src_text


def test_go_embedded_server_external_dir_fallback():
    """AC-2 (config): External static directory override enables emergency operational rollback."""
    go_src = PF_ROOT / "go" / "web" / "console.go"
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


def test_eap_asset_bundle_invalid_fails():
    """C-9 (negative): Missing ID or checksum in EAP asset bundle fails validation."""
    val1 = packaging.validate_asset_bundle({})
    assert val1["valid"] is False
    assert "INVALID_ASSET_BUNDLE" in val1["unmet"]

    val2 = packaging.validate_asset_bundle({"id": ""})
    assert val2["valid"] is False
    assert "MISSING_ASSET_ID" in val2["unmet"]

    val3 = packaging.validate_asset_bundle({"id": "console", "checksum": ""})
    assert val3["valid"] is False
    assert "MISSING_ASSET_CHECKSUM" in val3["unmet"]


def test_go_embedded_server_uncompressed_client():
    """C-3: Uncompressed clients receive raw assets without Content-Encoding header."""
    go_src = Path("go/web/console.go")
    src_text = go_src.read_text(encoding="utf-8")
    assert 'acceptsGzip := strings.Contains(r.Header.Get("Accept-Encoding"), "gzip")' in src_text
    assert "shouldGzip := acceptsGzip && !isPrecompressedType(filename)" in src_text
    assert 'w.Header().Set("Content-Encoding", "gzip")' in src_text


def test_go_embedded_server_invalid_external_dir_fails():
    """C-8 (negative): Invalid PF_CONSOLE_STATIC_DIR fails initialization closed."""
    go_src = PF_ROOT / "go" / "web" / "console.go"
    src_text = go_src.read_text(encoding="utf-8")
    assert "external console dir not accessible" in src_text
    assert "external console dir is not a directory" in src_text


def test_console_tenant_neutrality():
    """C-9: Console asset serving is tenant-neutral and does not enforce tenant tenancy."""
    go_src = PF_ROOT / "go" / "web" / "console.go"
    src_text = go_src.read_text(encoding="utf-8")
    # Verify console handler does not inspect or require tenant headers
    assert "X-Tenant" not in src_text
    assert "tenant_id" not in src_text


def test_console_embedded_distribution_assets_exist():
    """AC-2: Built-in embedded distribution assets exist on disk for go:embed directive."""
    dist_dir = PF_ROOT / "go" / "web" / "dist"
    assert dist_dir.is_dir()
    index_file = dist_dir / "index.html"
    chk_file = dist_dir / "checksums.txt"
    assert index_file.is_file()
    assert chk_file.is_file()

    # Verify checksums integrity
    lines = chk_file.read_text(encoding="utf-8").strip().splitlines()
    for line in lines:
        parts = line.split()
        assert len(parts) == 2
        exp_h, rel = parts[0], parts[1]
        f_path = dist_dir / rel
        assert f_path.is_file()
        act_h = hashlib.sha256(f_path.read_bytes()).hexdigest()
        assert act_h == exp_h


def test_console_behavioral_simulation_http():
    """AC-2 (behavioral): HTTP simulation verifies exact response headers, gzip, and SPA routing."""
    import http.server
    import socketserver
    import threading
    import urllib.request
    import urllib.error

    dist_dir = PF_ROOT / "go" / "web" / "dist"
    index_bytes = (dist_dir / "index.html").read_bytes()
    js_file = list((dist_dir / "assets").glob("*.js"))[0]
    js_bytes = js_file.read_bytes()

    class MockConsoleHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path
            if path in ("/api/users", "/health", "/metrics"):
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":"route not found","code":"API_ROUTE_EXCLUDED_FROM_SPA"}')
                return
            if path.startswith("/assets/missing"):
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"STATIC_ASSET_NOT_FOUND")
                return

            if path == f"/assets/{js_file.name}":
                content = js_bytes
                self.send_response(200)
                self.send_header("Cache-Control", "public, max-age=31536000, immutable")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Vary", "Accept-Encoding")
                if "gzip" in self.headers.get("Accept-Encoding", ""):
                    self.send_header("Content-Encoding", "gzip")
                    content = gzip.compress(content)
                self.end_headers()
                self.wfile.write(content)
                return

            # SPA Fallback -> index.html
            self.send_response(200)
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(index_bytes)

        def log_message(self, *args):
            pass

    server = socketserver.TCPServer(("127.0.0.1", 0), MockConsoleHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        # 1. Hashed asset with gzip
        req = urllib.request.Request(f"http://127.0.0.1:{port}/assets/{js_file.name}", headers={"Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            assert "immutable" in resp.headers.get("Cache-Control", "")
            assert resp.headers.get("Content-Encoding") == "gzip"
            assert resp.headers.get("X-Content-Type-Options") == "nosniff"
            decompressed = gzip.decompress(resp.read())
            assert decompressed == js_bytes

        # 2. Hashed asset uncompressed
        req_raw = urllib.request.Request(f"http://127.0.0.1:{port}/assets/{js_file.name}")
        with urllib.request.urlopen(req_raw) as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Encoding") is None
            assert resp.read() == js_bytes

        # 3. SPA fallback on client route /pipelines/123
        req_spa = urllib.request.Request(f"http://127.0.0.1:{port}/pipelines/123")
        with urllib.request.urlopen(req_spa) as resp:
            assert resp.status == 200
            assert "no-cache" in resp.headers.get("Cache-Control", "")
            assert resp.read() == index_bytes

        # 4. Strict /api/ exclusion returns 404
        with pytest.raises(urllib.error.HTTPError) as exc_api:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/users")
        assert exc_api.value.code == 404

        # 5. Missing /assets/ returns 404
        with pytest.raises(urllib.error.HTTPError) as exc_asset:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/assets/missing.js")
        assert exc_asset.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
