// Package objstorerest is the shared, dependency-free (stdlib-only) REST core for ObjectStore adapters that
// speak a provider HTTP API (GCS, Azure Blob, Google Drive, ...). It owns the cross-cutting concerns an
// adapter must NOT re-implement: an auth/token seam, bounded retry/backoff (honoring Retry-After), context
// deadlines, a portable error taxonomy, and secret redaction. Each adapter maps the provider's REST shape to
// datastore.ObjectStore on top of this Client.
package objstorerest

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

// Portable error taxonomy: adapters return these so callers degrade portably regardless of provider.
var (
	ErrNotFound  = errors.New("objstorerest: object not found")
	ErrForbidden = errors.New("objstorerest: access forbidden")
	ErrThrottled = errors.New("objstorerest: throttled")
	ErrConflict  = errors.New("objstorerest: conflict")
)

// Auth authorizes an outgoing request (bearer token, HMAC signature, OAuth refresh, ...). It MUST NOT log or
// return secrets. A nil Auth leaves requests unauthenticated (local/emulated providers, tests).
type Auth interface {
	Authorize(ctx context.Context, req *http.Request) error
}

// Config configures a Client.
type Config struct {
	BaseURL    string       // e.g. https://storage.googleapis.com (no trailing slash)
	Auth       Auth         // optional
	HTTPClient *http.Client // optional; default with timeout + sane transport
	MaxRetries int          // retries on throttling/5xx; default 3
	UserAgent  string
}

// Client is a retrying, auth-aware HTTP client for object-store REST APIs.
type Client struct {
	base       string
	auth       Auth
	http       *http.Client
	maxRetries int
	userAgent  string
}

// New builds a Client (fail-closed on a missing base URL).
func New(cfg Config) (*Client, error) {
	if strings.TrimSpace(cfg.BaseURL) == "" {
		return nil, errors.New("objstorerest: BaseURL is required")
	}
	hc := cfg.HTTPClient
	if hc == nil {
		hc = &http.Client{Timeout: 5 * time.Minute}
	}
	mr := cfg.MaxRetries
	if mr <= 0 {
		mr = 3
	}
	ua := cfg.UserAgent
	if ua == "" {
		ua = "productforge-objstorerest/1"
	}
	return &Client{
		base: strings.TrimRight(cfg.BaseURL, "/"), auth: cfg.Auth, http: hc, maxRetries: mr, userAgent: ua,
	}, nil
}

// BaseURL returns the configured base (no trailing slash).
func (c *Client) BaseURL() string { return c.base }

// Do performs the request, applying auth, context cancellation, and bounded retry/backoff on throttling
// (429) or 5xx responses. `rewind` (optional) returns a fresh body for a retry attempt; without it, a
// request with a body is NOT retried (so a non-seekable stream can never be silently truncated).
func (c *Client) Do(ctx context.Context, method, rawURL string, body io.Reader, rewind func() (io.Reader, error),
	headers map[string]string) (*http.Response, error) {
	var lastErr error
	for attempt := 0; attempt <= c.maxRetries; attempt++ {
		if attempt > 0 {
			if rewind == nil {
				return nil, fmt.Errorf("objstorerest: %s %s: not retried (no rewindable body): %w", method, Redact(rawURL), lastErr)
			}
			b, err := rewind()
			if err != nil {
				return nil, err
			}
			body = b
		}
		req, err := http.NewRequestWithContext(ctx, method, rawURL, body)
		if err != nil {
			return nil, err
		}
		req.Header.Set("User-Agent", c.userAgent)
		for k, v := range headers {
			req.Header.Set(k, v)
		}
		if c.auth != nil {
			if err := c.auth.Authorize(ctx, req); err != nil {
				return nil, fmt.Errorf("objstorerest: authorize: %w", err)
			}
		}
		resp, err := c.http.Do(req)
		if err != nil {
			lastErr = err
			if ctx.Err() != nil {
				return nil, err
			}
			if attempt < c.maxRetries {
				backoff(ctx, attempt, "")
				continue
			}
			return nil, err
		}
		if retryable(resp.StatusCode) && attempt < c.maxRetries {
			ra := resp.Header.Get("Retry-After")
			_, _ = io.Copy(io.Discard, resp.Body)
			_ = resp.Body.Close()
			backoff(ctx, attempt, ra)
			lastErr = Classify(resp.StatusCode)
			continue
		}
		return resp, nil
	}
	if lastErr == nil {
		lastErr = ErrThrottled
	}
	return nil, lastErr
}

func retryable(status int) bool {
	return status == 429 || (status >= 500 && status <= 599)
}

func backoff(ctx context.Context, attempt int, retryAfter string) {
	d := time.Duration(1<<uint(attempt)) * 200 * time.Millisecond // 200ms, 400ms, 800ms, ...
	if d > 5*time.Second {
		d = 5 * time.Second
	}
	if secs, err := strconv.Atoi(strings.TrimSpace(retryAfter)); err == nil && secs > 0 {
		d = time.Duration(secs) * time.Second
	}
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
	case <-t.C:
	}
}

// Classify maps an HTTP status to a portable sentinel (nil when no error class applies).
func Classify(status int) error {
	switch {
	case status == http.StatusNotFound:
		return ErrNotFound
	case status == http.StatusUnauthorized || status == http.StatusForbidden:
		return ErrForbidden
	case status == http.StatusConflict || status == http.StatusPreconditionFailed:
		return ErrConflict
	case status == http.StatusTooManyRequests || (status >= 500 && status <= 599):
		return ErrThrottled
	default:
		return nil
	}
}

// EnsureOK returns a portable error (with a redacted, truncated body) for a non-2xx response.
func (c *Client) EnsureOK(resp *http.Response) error {
	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		return nil
	}
	snippet, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
	_ = resp.Body.Close()
	if e := Classify(resp.StatusCode); e != nil {
		return fmt.Errorf("%w (%d): %s", e, resp.StatusCode, Redact(string(snippet)))
	}
	return fmt.Errorf("objstorerest: unexpected status %d: %s", resp.StatusCode, Redact(string(snippet)))
}

// SHA256Hex returns the hex sha256 of b (object checksums; content-addressed, provider-independent).
func SHA256Hex(b []byte) string {
	s := sha256.Sum256(b)
	return hex.EncodeToString(s[:])
}

// Redact removes obviously sensitive query params/tokens from a string before it is logged or returned.
func Redact(s string) string {
	if u, err := url.Parse(s); err == nil && u.RawQuery != "" {
		q := u.Query()
		for k := range q {
			lk := strings.ToLower(k)
			if strings.Contains(lk, "sig") || strings.Contains(lk, "token") || strings.Contains(lk, "key") ||
				strings.Contains(lk, "secret") || strings.Contains(lk, "credential") {
				q.Set(k, "REDACTED")
			}
		}
		u.RawQuery = q.Encode()
		return u.String()
	}
	return s
}
