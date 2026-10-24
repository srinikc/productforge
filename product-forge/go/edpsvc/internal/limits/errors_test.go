package limits

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestWriteErrorEnvelopeAndRedaction(t *testing.T) {
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/x", nil)
	req = req.WithContext(WithRequestID(req.Context(), "rid-1"))
	WriteError(rr, req, http.StatusTooManyRequests, "token=abc exceeded")
	if rr.Code != http.StatusTooManyRequests {
		t.Fatalf("status %d", rr.Code)
	}
	if rr.Header().Get("X-Request-ID") != "rid-1" {
		t.Fatalf("request id header %q", rr.Header().Get("X-Request-ID"))
	}
	var env ErrorEnvelope
	if err := json.Unmarshal(rr.Body.Bytes(), &env); err != nil {
		t.Fatal(err)
	}
	if env.Error.Code != "RATE_LIMITED" || !env.Error.Retryable || env.Error.RequestID != "rid-1" {
		t.Fatalf("unexpected envelope %+v", env.Error)
	}
	if strings.Contains(env.Error.Message, "abc") || !strings.Contains(env.Error.Message, "token=[REDACTED]") {
		t.Fatalf("message not redacted: %q", env.Error.Message)
	}
	if Redact("admin authorization required") != "admin authorization required" {
		t.Fatalf("plain prose must not be redacted: %q", Redact("admin authorization required"))
	}
	if Redact("Bearer abc.def") != "Bearer [REDACTED]" {
		t.Fatalf("bearer token not redacted: %q", Redact("Bearer abc.def"))
	}
}

func TestValidRequestID(t *testing.T) {
	for _, ok := range []string{"abc", "a.b_c-1", strings.Repeat("a", 128)} {
		if !ValidRequestID(ok) {
			t.Fatalf("%q should be valid", ok)
		}
	}
	for _, bad := range []string{"", "a b", "a|b", strings.Repeat("a", 129)} {
		if ValidRequestID(bad) {
			t.Fatalf("%q should be invalid", bad)
		}
	}
}

func TestWriteHandlerErrorMapping(t *testing.T) {
	cases := []struct {
		err  error
		code int
	}{
		{&http.MaxBytesError{Limit: 1}, http.StatusRequestEntityTooLarge},
		{context.DeadlineExceeded, http.StatusGatewayTimeout},
		{context.Canceled, http.StatusGatewayTimeout},
		{context.Canceled, http.StatusGatewayTimeout},
	}
	for _, tc := range cases {
		rr := httptest.NewRecorder()
		WriteHandlerError(rr, httptest.NewRequest(http.MethodGet, "/", nil), tc.err)
		if rr.Code != tc.code {
			t.Fatalf("%v: want %d, got %d", tc.err, tc.code, rr.Code)
		}
	}
}
