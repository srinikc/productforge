package web

import (
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"testing/fstest"
)

func mockConsoleFS() fstest.MapFS {
	indexHTML := []byte("<!DOCTYPE html><html><head><title>Product Forge Console</title></head><body><div id=\"root\"></div></body></html>")
	mainJS := []byte("console.log('Product Forge Web Console Initialized');")
	mainCSS := []byte("body { margin: 0; font-family: sans-serif; }")
	iconPNG := []byte("\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRmockpng")

	hIndex := sha256.Sum256(indexHTML)
	hJS := sha256.Sum256(mainJS)
	hCSS := sha256.Sum256(mainCSS)
	hPNG := sha256.Sum256(iconPNG)

	checksums := fmt.Sprintf(
		"%s  index.html\n%s  assets/main.1a2b3c.js\n%s  assets/main.4d5e6f.css\n%s  assets/icon.png\n",
		hex.EncodeToString(hIndex[:]),
		hex.EncodeToString(hJS[:]),
		hex.EncodeToString(hCSS[:]),
		hex.EncodeToString(hPNG[:]),
	)

	return fstest.MapFS{
		"index.html":             {Data: indexHTML},
		"assets/main.1a2b3c.js":  {Data: mainJS},
		"assets/main.4d5e6f.css": {Data: mainCSS},
		"assets/icon.png":        {Data: iconPNG},
		"checksums.txt":          {Data: []byte(checksums)},
	}
}

func TestNewConsoleHandler_IntegritySuccess(t *testing.T) {
	fsys := mockConsoleFS()
	handler, err := NewConsoleHandler(fsys, "", ConsoleConfig{})
	if err != nil {
		t.Fatalf("unexpected error creating console handler: %v", err)
	}
	if handler == nil {
		t.Fatal("expected non-nil handler")
	}
}

func TestNewConsoleHandler_IntegrityTamperFails(t *testing.T) {
	fsys := mockConsoleFS()
	// Tamper with index.html content
	fsys["index.html"] = &fstest.MapFile{Data: []byte("tampered content")}

	_, err := NewConsoleHandler(fsys, "", ConsoleConfig{})
	if err == nil {
		t.Fatal("expected integrity check failure on tampered content, got nil")
	}
	if !strings.Contains(err.Error(), ErrCodeAssetIntegrityMismatch) {
		t.Fatalf("expected error containing %s, got: %v", ErrCodeAssetIntegrityMismatch, err)
	}
}

func TestConsoleHandler_SPAFallback(t *testing.T) {
	fsys := mockConsoleFS()
	handler, err := NewConsoleHandler(fsys, "", ConsoleConfig{})
	if err != nil {
		t.Fatalf("failed to create handler: %v", err)
	}

	routes := []string{"/", "/console", "/pipelines/view", "/settings/auth"}
	for _, route := range routes {
		req := httptest.NewRequest(http.MethodGet, route, nil)
		rec := httptest.NewRecorder()

		handler.ServeHTTP(rec, req)

		if rec.Code != http.StatusOK {
			t.Errorf("route %s: expected status 200, got %d", route, rec.Code)
		}
		if !strings.Contains(rec.Body.String(), "<div id=\"root\"></div>") {
			t.Errorf("route %s: expected index.html content", route)
		}
		cacheControl := rec.Header().Get("Cache-Control")
		if !strings.Contains(cacheControl, "no-cache") {
			t.Errorf("route %s: expected Cache-Control no-cache, got %s", route, cacheControl)
		}
	}
}

func TestConsoleHandler_MissingStaticAssetReturns404(t *testing.T) {
	fsys := mockConsoleFS()
	handler, err := NewConsoleHandler(fsys, "", ConsoleConfig{})
	if err != nil {
		t.Fatalf("failed to create handler: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/assets/missing-bundle.999.js", nil)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Fatalf("expected 404 for missing static asset, got %d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), ErrCodeStaticAssetNotFound) {
		t.Fatalf("expected error body containing %s, got: %s", ErrCodeStaticAssetNotFound, rec.Body.String())
	}
}

func TestConsoleHandler_APIExclusionReturns404JSON(t *testing.T) {
	fsys := mockConsoleFS()
	handler, err := NewConsoleHandler(fsys, "", ConsoleConfig{})
	if err != nil {
		t.Fatalf("failed to create handler: %v", err)
	}

	apiRoutes := []string{"/api/v1/backlog/items", "/api/v1/health", "/health", "/metrics"}
	for _, route := range apiRoutes {
		req := httptest.NewRequest(http.MethodGet, route, nil)
		rec := httptest.NewRecorder()

		handler.ServeHTTP(rec, req)

		if rec.Code != http.StatusNotFound {
			t.Errorf("expected 404 for API route %s, got %d", route, rec.Code)
		}
		contentType := rec.Header().Get("Content-Type")
		if !strings.Contains(contentType, "application/json") {
			t.Errorf("expected application/json for API route %s, got %s", route, contentType)
		}
		if !strings.Contains(rec.Body.String(), ErrCodeAPIRouteExcluded) {
			t.Errorf("expected JSON containing %s, got %s", ErrCodeAPIRouteExcluded, rec.Body.String())
		}
	}
}

func TestConsoleHandler_GzipAndHeaders(t *testing.T) {
	fsys := mockConsoleFS()
	handler, err := NewConsoleHandler(fsys, "", ConsoleConfig{})
	if err != nil {
		t.Fatalf("failed to create handler: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/assets/main.1a2b3c.js", nil)
	req.Header.Set("Accept-Encoding", "gzip, deflate")
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rec.Code)
	}
	if rec.Header().Get("Content-Encoding") != "gzip" {
		t.Fatalf("expected Content-Encoding gzip, got %s", rec.Header().Get("Content-Encoding"))
	}
	if rec.Header().Get("Vary") != "Accept-Encoding" {
		t.Fatalf("expected Vary Accept-Encoding, got %s", rec.Header().Get("Vary"))
	}
	if rec.Header().Get("X-Content-Type-Options") != "nosniff" {
		t.Fatalf("expected X-Content-Type-Options nosniff, got %s", rec.Header().Get("X-Content-Type-Options"))
	}
	cacheControl := rec.Header().Get("Cache-Control")
	if !strings.Contains(cacheControl, "immutable") {
		t.Fatalf("expected Cache-Control immutable for hashed asset, got %s", cacheControl)
	}

	// Decompress and verify content
	gr, err := gzip.NewReader(rec.Body)
	if err != nil {
		t.Fatalf("failed to create gzip reader: %v", err)
	}
	decompressed, err := io.ReadAll(gr)
	if err != nil {
		t.Fatalf("failed to decompress body: %v", err)
	}
	if !strings.Contains(string(decompressed), "Product Forge Web Console Initialized") {
		t.Fatalf("unexpected decompressed content: %s", string(decompressed))
	}
}

func TestConsoleHandler_SkipGzipOnPrecompressedMedia(t *testing.T) {
	fsys := mockConsoleFS()
	handler, err := NewConsoleHandler(fsys, "", ConsoleConfig{})
	if err != nil {
		t.Fatalf("failed to create handler: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/assets/icon.png", nil)
	req.Header.Set("Accept-Encoding", "gzip, deflate")
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rec.Code)
	}
	if rec.Header().Get("Content-Encoding") == "gzip" {
		t.Fatalf("expected PNG not to be gzipped, but Content-Encoding was gzip")
	}
}

func TestConsoleHandler_PathTraversalBlocked(t *testing.T) {
	fsys := mockConsoleFS()
	handler, err := NewConsoleHandler(fsys, "", ConsoleConfig{})
	if err != nil {
		t.Fatalf("failed to create handler: %v", err)
	}

	traversalPaths := []string{"/../etc/passwd", "/assets/../../secret", "/.."}
	for _, p := range traversalPaths {
		req := httptest.NewRequest(http.MethodGet, p, nil)
		rec := httptest.NewRecorder()

		handler.ServeHTTP(rec, req)

		if rec.Code != http.StatusBadRequest && rec.Code != http.StatusNotFound {
			t.Errorf("path %s: expected 400 or 404, got %d", p, rec.Code)
		}
	}
}

func TestConsoleHandler_ExternalDirRollback(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "console_external_*")
	if err != nil {
		t.Fatalf("failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	externalHTML := []byte("<html><body>Rollback Static Console</body></html>")
	if err := os.WriteFile(filepath.Join(tmpDir, "index.html"), externalHTML, 0644); err != nil {
		t.Fatalf("failed to write external index.html: %v", err)
	}
	hIndex := sha256.Sum256(externalHTML)
	chkManifest := fmt.Sprintf("%s  index.html\n", hex.EncodeToString(hIndex[:]))
	if err := os.WriteFile(filepath.Join(tmpDir, "checksums.txt"), []byte(chkManifest), 0644); err != nil {
		t.Fatalf("failed to write external checksums.txt: %v", err)
	}

	handler, err := NewConsoleHandler(mockConsoleFS(), "", ConsoleConfig{
		ExternalDir: tmpDir,
	})
	if err != nil {
		t.Fatalf("failed to create handler with external dir: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/", nil)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 from external dir, got %d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), "Rollback Static Console") {
		t.Fatalf("expected content from external dir, got: %s", rec.Body.String())
	}
}

func TestNewEmbeddedConsoleHandler(t *testing.T) {
	handler, err := NewEmbeddedConsoleHandler()
	if err != nil {
		t.Fatalf("unexpected error creating embedded console handler: %v", err)
	}
	if handler == nil {
		t.Fatal("expected non-nil handler")
	}

	req := httptest.NewRequest(http.MethodGet, "/", nil)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200 from embedded handler, got %d", rec.Code)
	}
}

func TestNewConsoleHandler_MissingChecksumsFailsClosed(t *testing.T) {
	fsys := mockConsoleFS()
	delete(fsys, "checksums.txt")

	_, err := NewConsoleHandler(fsys, "", ConsoleConfig{})
	if err == nil {
		t.Fatal("expected error when checksums.txt is missing, got nil")
	}
	if !strings.Contains(err.Error(), ErrCodeAssetIntegrityMismatch) {
		t.Fatalf("expected ErrCodeAssetIntegrityMismatch, got: %v", err)
	}
}

func TestNewConsoleHandler_UnlistedAssetFailsClosed(t *testing.T) {
	fsys := mockConsoleFS()
	fsys["assets/unlisted.js"] = &fstest.MapFile{Data: []byte("console.log('rogue');")}

	_, err := NewConsoleHandler(fsys, "", ConsoleConfig{})
	if err == nil {
		t.Fatal("expected error for unlisted asset in bundle, got nil")
	}
	if !strings.Contains(err.Error(), "unlisted asset detected") {
		t.Fatalf("expected unlisted asset error, got: %v", err)
	}
}

func TestConsoleHandler_UncompressedClient(t *testing.T) {
	fsys := mockConsoleFS()
	handler, err := NewConsoleHandler(fsys, "", ConsoleConfig{})
	if err != nil {
		t.Fatalf("failed to create handler: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/assets/main.1a2b3c.js", nil)
	// No Accept-Encoding header set
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rec.Code)
	}
	if rec.Header().Get("Content-Encoding") != "" {
		t.Fatalf("expected no Content-Encoding for uncompressed client, got: %s", rec.Header().Get("Content-Encoding"))
	}
	if !strings.Contains(rec.Body.String(), "Product Forge Web Console Initialized") {
		t.Fatalf("expected uncompressed body content")
	}
}

func TestConsoleHandler_InvalidExternalDirFails(t *testing.T) {
	_, err := NewConsoleHandler(mockConsoleFS(), "", ConsoleConfig{
		ExternalDir: "/nonexistent/static/path/that/cannot/exist",
	})
	if err == nil {
		t.Fatal("expected error for non-existent external dir, got nil")
	}
}

func TestConsoleHandler_CacheHeaderDistinction(t *testing.T) {
	fsys := mockConsoleFS()
	handler, err := NewConsoleHandler(fsys, "", ConsoleConfig{})
	if err != nil {
		t.Fatalf("failed to create handler: %v", err)
	}

	// 1. Content-hashed asset -> immutable
	req1 := httptest.NewRequest(http.MethodGet, "/assets/main.1a2b3c.js", nil)
	rec1 := httptest.NewRecorder()
	handler.ServeHTTP(rec1, req1)
	cc1 := rec1.Header().Get("Cache-Control")
	if !strings.Contains(cc1, "immutable") {
		t.Errorf("expected immutable cache header for hashed asset, got %s", cc1)
	}

	// 2. Non-hashed asset -> must-revalidate
	req2 := httptest.NewRequest(http.MethodGet, "/assets/icon.png", nil)
	rec2 := httptest.NewRecorder()
	handler.ServeHTTP(rec2, req2)
	cc2 := rec2.Header().Get("Cache-Control")
	if !strings.Contains(cc2, "must-revalidate") || strings.Contains(cc2, "immutable") {
		t.Errorf("expected must-revalidate (not immutable) for non-hashed asset, got %s", cc2)
	}

	// 3. index.html -> no-cache
	req3 := httptest.NewRequest(http.MethodGet, "/", nil)
	rec3 := httptest.NewRecorder()
	handler.ServeHTTP(rec3, req3)
	cc3 := rec3.Header().Get("Cache-Control")
	if !strings.Contains(cc3, "no-cache") {
		t.Errorf("expected no-cache for index.html, got %s", cc3)
	}
}
