package limits

import (
	"context"
	"crypto/rand"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"regexp"
	"strings"
)

type ctxKey string

const requestIDKey ctxKey = "edp-request-id"

var (
	requestIDRE = regexp.MustCompile(`^[A-Za-z0-9._-]{1,128}$`)
	secretRE    = regexp.MustCompile(`(?i)\b(api[_-]?key|token|secret|password|authorization)\b\s*[:=]\s*\S+`)
	bearerRE    = regexp.MustCompile(`(?i)\b(bearer)\s+\S+`)
)

// NewRequestID returns a UUIDv4 request id.
func NewRequestID() string {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "req-unknown"
	}
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
}

// ValidRequestID accepts a bounded, log-safe inbound id.
func ValidRequestID(id string) bool { return requestIDRE.MatchString(id) }

// WithRequestID stores the request id on the context.
func WithRequestID(ctx context.Context, id string) context.Context {
	return context.WithValue(ctx, requestIDKey, id)
}

// RequestIDFrom reads the request id (empty when absent).
func RequestIDFrom(ctx context.Context) string {
	if ctx == nil {
		return ""
	}
	id, _ := ctx.Value(requestIDKey).(string)
	return id
}

// Redact masks token/secret-like values in a client-visible message without mangling ordinary prose.
func Redact(s string) string {
	s = secretRE.ReplaceAllString(s, "$1=[REDACTED]")
	return bearerRE.ReplaceAllString(s, "$1 [REDACTED]")
}

// ErrorPayload is the stable v1 error body.
type ErrorPayload struct {
	Code      string `json:"code"`
	Message   string `json:"message"`
	Category  string `json:"category"`
	Retryable bool   `json:"retryable"`
	RequestID string `json:"request_id"`
}

// ErrorEnvelope is the v1 error envelope.
type ErrorEnvelope struct {
	Version string       `json:"version"`
	Error   ErrorPayload `json:"error"`
}

var statusCodes = map[int]struct {
	code      string
	category  string
	retryable bool
}{
	400: {"BAD_REQUEST", "client", false},
	401: {"UNAUTHENTICATED", "auth", false},
	403: {"FORBIDDEN", "auth", false},
	404: {"NOT_FOUND", "client", false},
	405: {"METHOD_NOT_ALLOWED", "client", false},
	408: {"TIMEOUT", "client", true},
	409: {"CONFLICT", "conflict", false},
	413: {"PAYLOAD_TOO_LARGE", "client", false},
	429: {"RATE_LIMITED", "rate_limit", true},
	500: {"INTERNAL", "server", false},
	503: {"DEPENDENCY_UNAVAILABLE", "dependency", true},
	504: {"TIMEOUT", "server", true},
}

// CodeForStatus maps an HTTP status to the stable error code/category/retryable.
func CodeForStatus(status int) (string, string, bool) {
	if m, ok := statusCodes[status]; ok {
		return m.code, m.category, m.retryable
	}
	return "INTERNAL", "server", false
}

// WriteError writes the v1 envelope for a status and a (redacted) message.
func WriteError(w http.ResponseWriter, r *http.Request, status int, message string) {
	code, category, retryable := CodeForStatus(status)
	WriteErrorCode(w, r, status, code, message, category, retryable)
}

// WriteErrorCode writes the v1 envelope with an explicit code/category/retryable.
func WriteErrorCode(w http.ResponseWriter, r *http.Request, status int, code, message, category string, retryable bool) {
	rid := ""
	if r != nil {
		rid = RequestIDFrom(r.Context())
		if rid == "" {
			rid = NewRequestID()
		}
		w.Header().Set("X-Request-ID", rid)
	}
	if strings.TrimSpace(message) == "" {
		message = code
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(ErrorEnvelope{Version: "1", Error: ErrorPayload{
		Code: code, Message: Redact(message), Category: category, Retryable: retryable, RequestID: rid}})
}

// WriteHandlerError maps a handler error to the envelope (413/504/500) without leaking internals.
func WriteHandlerError(w http.ResponseWriter, r *http.Request, err error) {
	var mbe *http.MaxBytesError
	switch {
	case errors.As(err, &mbe):
		WriteError(w, r, http.StatusRequestEntityTooLarge, "request body exceeds the configured limit")
	case errors.Is(err, context.DeadlineExceeded):
		WriteError(w, r, http.StatusGatewayTimeout, "request timed out")
	case errors.Is(err, context.Canceled):
		WriteError(w, r, http.StatusGatewayTimeout, "request canceled")
	default:
		WriteError(w, r, http.StatusInternalServerError, "internal error")
	}
}
