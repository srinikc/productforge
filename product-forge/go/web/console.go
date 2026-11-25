package web

import (
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"net/http"
	"os"
	"path"
	"path/filepath"
	"strings"
)

// ConsoleConfig defines configuration for the embedded web console server.
type ConsoleConfig struct {
	ExternalDir        string // Optional override directory for static assets (PF_CONSOLE_STATIC_DIR)
	DistSubdir         string // Subdirectory within embedded FS where assets reside (e.g. "dist/console")
	SkipGzipCompressed bool   // Whether to skip gzip compression for precompressed media types
}

// ConsoleHandler implements the HTTP handler serving embedded or external web console assets.
type ConsoleHandler struct {
	fileSystem http.FileSystem
	rawFS      fs.FS
	isExternal bool
	config     ConsoleConfig
}

// Error codes matching the durable design pack failure matrix.
const (
	ErrCodeAssetIntegrityMismatch = "ASSET_INTEGRITY_MISMATCH"
	ErrCodePathTraversalBlocked   = "PATH_TRAVERSAL_BLOCKED"
	ErrCodeStaticAssetNotFound    = "STATIC_ASSET_NOT_FOUND"
	ErrCodeAPIRouteExcluded       = "API_ROUTE_EXCLUDED_FROM_SPA"
	ErrCodeSourceMapDetected      = "SOURCE_MAP_DETECTED"
)

// ValidateConsoleRoutePath validates that a requested URL path does not perform directory traversal.
func ValidateConsoleRoutePath(urlPath string) (string, error) {
	clean := path.Clean("/" + strings.TrimPrefix(urlPath, "/"))
	if strings.Contains(urlPath, "..") || strings.HasPrefix(clean, "/../") || clean == "/.." {
		return "", fmt.Errorf("%s: path traversal attempted: %s", ErrCodePathTraversalBlocked, urlPath)
	}
	return clean, nil
}

// IsAPIRoute checks if the requested path belongs to the API or platform health/metrics endpoints.
func IsAPIRoute(urlPath string) bool {
	clean := path.Clean("/" + strings.TrimPrefix(urlPath, "/"))
	return strings.HasPrefix(clean, "/api/") || clean == "/api" ||
		strings.HasPrefix(clean, "/health") ||
		strings.HasPrefix(clean, "/metrics")
}

// ResolveConsoleFileSystem determines whether to serve from external directory or embedded filesystem.
func ResolveConsoleFileSystem(embeddedFS fs.FS, distSubdir string, externalDir string) (fs.FS, bool, error) {
	extDir := strings.TrimSpace(externalDir)
	if extDir == "" {
		extDir = strings.TrimSpace(os.Getenv("PF_CONSOLE_STATIC_DIR"))
	}
	if extDir != "" {
		stat, err := os.Stat(extDir)
		if err != nil {
			return nil, false, fmt.Errorf("external console dir not accessible: %w", err)
		}
		if !stat.IsDir() {
			return nil, false, fmt.Errorf("external console dir is not a directory: %s", extDir)
		}
		return os.DirFS(extDir), true, nil
	}

	if distSubdir != "" && distSubdir != "." {
		sub, err := fs.Sub(embeddedFS, distSubdir)
		if err != nil {
			return nil, false, fmt.Errorf("failed to resolve embedded sub-filesystem %s: %w", distSubdir, err)
		}
		return sub, false, nil
	}
	return embeddedFS, false, nil
}

// VerifyAssetIntegrity verifies files against checksums.txt in the target filesystem.
func VerifyAssetIntegrity(sys fs.FS) error {
	data, err := fs.ReadFile(sys, "checksums.txt")
	if err != nil {
		if errors.Is(err, fs.ErrNotExist) {
			return nil
		}
		return fmt.Errorf("%s: failed to read checksums.txt: %w", ErrCodeAssetIntegrityMismatch, err)
	}

	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.Fields(line)
		if len(parts) < 2 {
			continue
		}
		expectedHash := parts[0]
		relPath := strings.TrimPrefix(parts[1], "./")
		if relPath == "checksums.txt" {
			continue
		}

		fileBytes, err := fs.ReadFile(sys, relPath)
		if err != nil {
			return fmt.Errorf("%s: missing expected asset %s: %w", ErrCodeAssetIntegrityMismatch, relPath, err)
		}
		h := sha256.Sum256(fileBytes)
		actualHash := hex.EncodeToString(h[:])
		if actualHash != expectedHash {
			return fmt.Errorf("%s: asset %s hash mismatch (expected %s, got %s)",
				ErrCodeAssetIntegrityMismatch, relPath, expectedHash, actualHash)
		}
	}
	return nil
}

// NewConsoleHandler constructs an HTTP handler serving embedded or external web console assets.
func NewConsoleHandler(embeddedFS fs.FS, distSubdir string, cfg ConsoleConfig) (*ConsoleHandler, error) {
	resolvedFS, isExt, err := ResolveConsoleFileSystem(embeddedFS, distSubdir, cfg.ExternalDir)
	if err != nil {
		return nil, err
	}

	// Embed-time startup integrity attestation (AC-1 / Invariant 1)
	if err := VerifyAssetIntegrity(resolvedFS); err != nil {
		return nil, err
	}

	return &ConsoleHandler{
		fileSystem: http.FS(resolvedFS),
		rawFS:      resolvedFS,
		isExternal: isExt,
		config:     cfg,
	}, nil
}

// isPrecompressedType returns true for binary assets that gain negligible benefit from gzip.
func isPrecompressedType(filePath string) bool {
	ext := strings.ToLower(filepath.Ext(filePath))
	switch ext {
	case ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".zip", ".gz", ".wasm":
		return true
	default:
		return false
	}
}

// ServeConsoleMux routes requests between API endpoints and embedded web console.
func ServeConsoleMux(apiHandler http.Handler, consoleHandler http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if IsAPIRoute(r.URL.Path) {
			if apiHandler != nil {
				apiHandler.ServeHTTP(w, r)
			} else {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusNotFound)
				_ = json.NewEncoder(w).Encode(map[string]string{
					"error": "api route not found",
					"code":  ErrCodeAPIRouteExcluded,
				})
			}
			return
		}
		consoleHandler.ServeHTTP(w, r)
	})
}

// ServeHTTP handles static asset serving, gzip compression, caching, and client-side SPA fallback.
func (h *ConsoleHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	cleanPath, err := ValidateConsoleRoutePath(r.URL.Path)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	// 1. Strict API route boundary protection (CL-016 / Invariant 4)
	if IsAPIRoute(cleanPath) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		_ = json.NewEncoder(w).Encode(map[string]string{
			"error": "route not found",
			"code":  ErrCodeAPIRouteExcluded,
		})
		return
	}

	// 2. Reject source map requests
	if strings.HasSuffix(cleanPath, ".map") {
		http.Error(w, "source maps forbidden", http.StatusNotFound)
		return
	}

	// 3. Set baseline security headers
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
	w.Header().Set("Vary", "Accept-Encoding")

	// 4. Check if exact asset exists in filesystem
	reqFile := strings.TrimPrefix(cleanPath, "/")
	if reqFile == "" {
		reqFile = "index.html"
	}

	f, err := h.rawFS.Open(reqFile)
	if err == nil {
		stat, statErr := f.Stat()
		if statErr == nil && !stat.IsDir() {
			defer f.Close()
			h.serveFileContent(w, r, reqFile, f, stat)
			return
		}
		_ = f.Close()
	}

	// 5. If missing and under /assets/, return 404 (do NOT fallback to index.html)
	if strings.HasPrefix(cleanPath, "/assets/") {
		http.Error(w, fmt.Sprintf("%s: static asset not found: %s", ErrCodeStaticAssetNotFound, cleanPath), http.StatusNotFound)
		return
	}

	// 6. SPA fallback for all other client routes -> serve index.html with 200 OK
	indexFile, err := h.rawFS.Open("index.html")
	if err != nil {
		http.Error(w, "index.html not found", http.StatusNotFound)
		return
	}
	defer indexFile.Close()
	stat, _ := indexFile.Stat()
	h.serveFileContent(w, r, "index.html", indexFile, stat)
}

func (h *ConsoleHandler) serveFileContent(w http.ResponseWriter, r *http.Request, filename string, rdr io.Reader, stat fs.FileInfo) {
	// Set Cache-Control
	if filename == "index.html" {
		w.Header().Set("Cache-Control", "no-cache, no-store, must-revalidate")
		w.Header().Set("Pragma", "no-cache")
		w.Header().Set("Expires", "0")
	} else if strings.HasPrefix(filename, "assets/") || strings.Contains(filename, ".") {
		w.Header().Set("Cache-Control", "public, max-age=31536000, immutable")
	}

	acceptsGzip := strings.Contains(r.Header.Get("Accept-Encoding"), "gzip")
	shouldGzip := acceptsGzip && !isPrecompressedType(filename)

	content, err := io.ReadAll(rdr)
	if err != nil {
		http.Error(w, "error reading file content", http.StatusInternalServerError)
		return
	}

	if shouldGzip {
		w.Header().Set("Content-Encoding", "gzip")
		var buf bytes.Buffer
		gw := gzip.NewWriter(&buf)
		_, _ = gw.Write(content)
		_ = gw.Close()
		content = buf.Bytes()
	}

	modTime := stat.ModTime()
	http.ServeContent(w, r, filename, modTime, bytes.NewReader(content))
}
