package limits

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"log"
	"math"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"
)

var tenantRE = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`)

// ValidTenant reports whether a tenant key is a safe, bounded label.
func ValidTenant(t string) bool { return tenantRE.MatchString(t) }

func isUpload(path string) bool { return path == "/artifacts" }

// EnvelopeFallback rewrites ServeMux's plain-text 404/405 responses into the v1 JSON envelope, so every
// response on the surface is structured.
func EnvelopeFallback(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		next.ServeHTTP(&fallbackWriter{ResponseWriter: w, r: r}, r)
	})
}

type fallbackWriter struct {
	http.ResponseWriter
	r           *http.Request
	intercepted bool
}

func (w *fallbackWriter) WriteHeader(code int) {
	if code == http.StatusNotFound || code == http.StatusMethodNotAllowed {
		w.intercepted = true
		msg := "not found"
		if code == http.StatusMethodNotAllowed {
			msg = "method not allowed"
		}
		WriteError(w.ResponseWriter, w.r, code, msg)
		return
	}
	w.ResponseWriter.WriteHeader(code)
}

func (w *fallbackWriter) Write(b []byte) (int, error) {
	if w.intercepted {
		return len(b), nil
	}
	return w.ResponseWriter.Write(b)
}

func (w *fallbackWriter) Flush() {
	if f, ok := w.ResponseWriter.(http.Flusher); ok {
		f.Flush()
	}
}

// peekJSONTenant reads a bounded JSON body to attribute a POST to the tenant it targets, then restores it.
func peekJSONTenant(r *http.Request) (string, error) {
	ct := strings.ToLower(r.Header.Get("Content-Type"))
	if r.Body == nil || (r.Method != http.MethodPost && r.Method != http.MethodPut &&
		r.Method != http.MethodPatch) || !strings.HasPrefix(ct, "application/json") {
		return "", nil
	}
	body, err := io.ReadAll(r.Body)
	if err != nil {
		return "", err
	}
	r.Body = io.NopCloser(bytes.NewReader(body))
	var v struct {
		Tenant string `json:"tenant"`
	}
	_ = json.Unmarshal(body, &v)
	return strings.TrimSpace(v.Tenant), nil
}
func isExempt(path string) bool {
	return path == "/health" || path == "/ready" || path == "/metrics"
}

// Chain composes the guardrail middleware. Order (outer to inner):
// RequestID -> Instrument -> Recover -> RoleGate -> Timeout -> BodyLimit -> Quota -> handler.
func Chain(next http.Handler, cfg Config, q *Quota, m *Metrics, roleOK func() bool) http.Handler {
	h := next
	if cfg.Enforce {
		h = quotaMiddleware(h, q)
		h = bodyLimitMiddleware(h, cfg)
		h = timeoutMiddleware(h, cfg)
	}
	h = roleGateMiddleware(h, roleOK)
	h = recoverMiddleware(h)
	h = instrumentMiddleware(h, m)
	return requestIDMiddleware(h)
}

type statusWriter struct {
	http.ResponseWriter
	status int
	wrote  bool
}

func (w *statusWriter) WriteHeader(code int) {
	if !w.wrote {
		w.status = code
		w.wrote = true
		w.ResponseWriter.WriteHeader(code)
	}
}

func (w *statusWriter) Write(b []byte) (int, error) {
	if !w.wrote {
		w.WriteHeader(http.StatusOK)
	}
	return w.ResponseWriter.Write(b)
}

// Flush forwards to the underlying writer when it supports streaming.
func (w *statusWriter) Flush() {
	if f, ok := w.ResponseWriter.(http.Flusher); ok {
		f.Flush()
	}
}

func requestIDMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id := strings.TrimSpace(r.Header.Get("X-Request-ID"))
		if !ValidRequestID(id) {
			id = NewRequestID()
		}
		w.Header().Set("X-Request-ID", id)
		next.ServeHTTP(w, r.WithContext(WithRequestID(r.Context(), id)))
	})
}

func instrumentMiddleware(next http.Handler, m *Metrics) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		sw := &statusWriter{ResponseWriter: w, status: http.StatusOK}
		start := time.Now()
		next.ServeHTTP(sw, r)
		class := "json"
		if isUpload(r.URL.Path) {
			class = "upload"
		}
		m.Observe(class, sw.status, time.Since(start))
	})
}

func recoverMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if rec := recover(); rec != nil {
				log.Printf("edpsvc: panic on %s %s: %v", r.Method, r.URL.Path, rec)
				WriteError(w, r, http.StatusInternalServerError, "internal error")
			}
		}()
		next.ServeHTTP(w, r)
	})
}

func roleGateMiddleware(next http.Handler, roleOK func() bool) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if isExempt(r.URL.Path) || roleOK == nil || roleOK() {
			next.ServeHTTP(w, r)
			return
		}
		WriteError(w, r, http.StatusServiceUnavailable, "runtime database role check failed")
	})
}

func timeoutMiddleware(next http.Handler, cfg Config) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		d := cfg.RequestTimeout
		if isUpload(r.URL.Path) {
			d = cfg.UploadTimeout
		}
		ctx, cancel := context.WithTimeout(r.Context(), d)
		defer cancel()
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func bodyLimitMiddleware(next http.Handler, cfg Config) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if isExempt(r.URL.Path) {
			next.ServeHTTP(w, r)
			return
		}
		limit := cfg.MaxBodyBytes
		if isUpload(r.URL.Path) {
			limit = cfg.MaxUploadBytes
		}
		if r.ContentLength > limit {
			WriteError(w, r, http.StatusRequestEntityTooLarge, "request body exceeds the configured limit")
			return
		}
		r.Body = http.MaxBytesReader(w, r.Body, limit)
		next.ServeHTTP(w, r)
	})
}

func quotaMiddleware(next http.Handler, q *Quota) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if isExempt(r.URL.Path) || q == nil {
			next.ServeHTTP(w, r)
			return
		}
		header := strings.TrimSpace(r.Header.Get("X-Tenant-Id"))
		query := strings.TrimSpace(r.URL.Query().Get("tenant"))
		if header != "" && !ValidTenant(header) {
			WriteError(w, r, http.StatusBadRequest, "invalid X-Tenant-Id")
			return
		}
		if header != "" && query != "" && header != query {
			WriteError(w, r, http.StatusBadRequest, "X-Tenant-Id does not match the tenant query parameter")
			return
		}
		bodyTenant, err := peekJSONTenant(r)
		if err != nil {
			WriteHandlerError(w, r, err)
			return
		}
		if header != "" && bodyTenant != "" && header != bodyTenant {
			WriteError(w, r, http.StatusBadRequest, "X-Tenant-Id does not match the body tenant")
			return
		}
		tenant := header
		if tenant == "" {
			tenant = query
		}
		if tenant == "" {
			tenant = bodyTenant
		}
		if tenant != "" && !ValidTenant(tenant) {
			WriteError(w, r, http.StatusBadRequest, "invalid tenant")
			return
		}
		d, release := q.Acquire(tenant)
		if !d.Allowed {
			secs := int(math.Ceil(d.RetryAfter.Seconds()))
			if secs < 1 {
				secs = 1
			}
			w.Header().Set("Retry-After", strconv.Itoa(secs))
			WriteErrorCode(w, r, http.StatusTooManyRequests, "RATE_LIMITED",
				"request quota exceeded ("+d.Scope+")", "rate_limit", true)
			return
		}
		defer release()
		next.ServeHTTP(w, r)
	})
}
