package eventtransport

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"

	"productforge/edpdata"
)

type Webhook struct {
	Client       *http.Client
	AllowHTTP    bool
	AllowPrivate bool
	Timeout      time.Duration
}

func NewWebhook() *Webhook {
	allowHTTP, _ := strconv.ParseBool(os.Getenv("PF_WEBHOOK_ALLOW_HTTP"))
	allowPrivate, _ := strconv.ParseBool(os.Getenv("PF_WEBHOOK_ALLOW_PRIVATE"))
	timeout := 10 * time.Second
	if s := os.Getenv("PF_WEBHOOK_TIMEOUT_SECONDS"); s != "" {
		if n, err := strconv.Atoi(s); err == nil && n > 0 {
			timeout = time.Duration(n) * time.Second
		}
	}
	return &Webhook{Client: &http.Client{Timeout: timeout, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}, AllowHTTP: allowHTTP, AllowPrivate: allowPrivate, Timeout: timeout}
}

func (w *Webhook) Deliver(ctx context.Context, sub edpdata.Subscription, ev edpdata.Event) error {
	key, ok := ResolveHMACKey(sub.AuthRef)
	if !ok {
		return edpdata.PermanentError{Err: fmt.Errorf("webhook HMAC key unavailable")}
	}
	u, err := validateTarget(sub.Target, w.AllowHTTP, w.AllowPrivate)
	if err != nil {
		return edpdata.PermanentError{Err: err}
	}
	body, err := json.Marshal(map[string]any{"event_id": ev.EventID, "type": ev.Type, "seq": ev.Seq, "tenant_id": ev.TenantID, "payload": json.RawMessage(ev.Payload)})
	if err != nil {
		return edpdata.PermanentError{Err: err}
	}
	ts := strconv.FormatInt(time.Now().Unix(), 10)
	mac := hmac.New(sha256.New, []byte(key))
	mac.Write([]byte(ts + "." + string(body)))
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, u.String(), bytes.NewReader(body))
	if err != nil {
		return edpdata.PermanentError{Err: err}
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-PF-Timestamp", ts)
	req.Header.Set("X-PF-Signature", "sha256="+hex.EncodeToString(mac.Sum(nil)))
	req.Header.Set("X-PF-Idempotency-Key", ev.EventID)
	resp, err := w.Client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, resp.Body)
	switch {
	case resp.StatusCode >= 200 && resp.StatusCode < 300:
		return nil
	case resp.StatusCode == 409:
		return nil
	case resp.StatusCode == 408 || resp.StatusCode == 425 || resp.StatusCode == 429 || resp.StatusCode >= 500:
		return fmt.Errorf("webhook transient status %d", resp.StatusCode)
	case resp.StatusCode == 401 || resp.StatusCode == 403:
		return fmt.Errorf("webhook auth status %d", resp.StatusCode)
	default:
		return edpdata.PermanentError{Err: fmt.Errorf("webhook permanent status %d", resp.StatusCode)}
	}
}

func validateTarget(raw string, allowHTTP, allowPrivate bool) (*url.URL, error) {
	u, err := url.Parse(raw)
	if err != nil || u.Host == "" {
		return nil, fmt.Errorf("invalid webhook target")
	}
	if u.Scheme != "https" && !(allowHTTP && u.Scheme == "http") {
		return nil, fmt.Errorf("webhook target must be https")
	}
	if !allowPrivate {
		host := u.Hostname()
		if host == "localhost" || host == "127.0.0.1" || host == "::1" {
			return nil, fmt.Errorf("private webhook target blocked")
		}
		if ip := net.ParseIP(host); ip != nil && (ip.IsLoopback() || ip.IsPrivate()) {
			return nil, fmt.Errorf("private webhook target blocked")
		}
	}
	return u, nil
}

var _ = strings.TrimSpace
