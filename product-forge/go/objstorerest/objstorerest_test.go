package objstorerest

import (
	"bytes"
	"context"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
)

func TestClassify(t *testing.T) {
	cases := map[int]error{
		404: ErrNotFound, 401: ErrForbidden, 403: ErrForbidden, 409: ErrConflict,
		412: ErrConflict, 429: ErrThrottled, 500: ErrThrottled, 503: ErrThrottled, 200: nil,
	}
	for status, want := range cases {
		if got := Classify(status); got != want {
			t.Fatalf("Classify(%d) = %v, want %v", status, got, want)
		}
	}
}

func TestRedact(t *testing.T) {
	out := Redact("https://x/o?X-Goog-Signature=SECRET&token=abc&keep=1")
	if strings.Contains(out, "SECRET") || strings.Contains(out, "abc") {
		t.Fatalf("secrets not redacted: %s", out)
	}
	if !strings.Contains(out, "keep=1") {
		t.Fatalf("non-secret param lost: %s", out)
	}
}

func TestRetryOn429ThenSuccess(t *testing.T) {
	var hits int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if atomic.AddInt32(&hits, 1) == 1 {
			w.Header().Set("Retry-After", "0")
			w.WriteHeader(http.StatusTooManyRequests)
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	}))
	defer srv.Close()
	c, _ := New(Config{BaseURL: srv.URL, MaxRetries: 2})
	body := []byte("payload")
	resp, err := c.Do(context.Background(), http.MethodPut, srv.URL+"/k", bytes.NewReader(body),
		func() (io.Reader, error) { return bytes.NewReader(body), nil }, nil)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK || atomic.LoadInt32(&hits) != 2 {
		t.Fatalf("want retried 200, got status=%d hits=%d", resp.StatusCode, hits)
	}
}

func TestNoRewindIsNotRetried(t *testing.T) {
	var hits int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&hits, 1)
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer srv.Close()
	c, _ := New(Config{BaseURL: srv.URL, MaxRetries: 3})
	_, err := c.Do(context.Background(), http.MethodPut, srv.URL+"/k", bytes.NewReader([]byte("x")), nil, nil)
	if err == nil || atomic.LoadInt32(&hits) != 1 {
		t.Fatalf("a non-rewindable body must NOT be retried: err=%v hits=%d", err, hits)
	}
}

func TestEnsureOKClassifies(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "nope", http.StatusNotFound)
	}))
	defer srv.Close()
	c, _ := New(Config{BaseURL: srv.URL})
	resp, err := http.Get(srv.URL + "/x")
	if err != nil {
		t.Fatal(err)
	}
	if e := c.EnsureOK(resp); !errors.Is(e, ErrNotFound) {
		t.Fatalf("EnsureOK(404) = %v, want ErrNotFound", e)
	}
}

func TestNewRequiresBaseURL(t *testing.T) {
	if _, err := New(Config{}); err == nil {
		t.Fatal("empty BaseURL must fail closed")
	}
}
