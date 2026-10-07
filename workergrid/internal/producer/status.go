// Stage 3c (BI-PF-0413): write execution status back to the producer.
package producer

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"time"
)

// SetStatus writes one backlog status transition:
// POST {base}/api/v1/backlog/items/{itemID}/status {status, note, scope, project}.
// Auth: bearer token + X-Roles: operator (api.auth.require_operator); the PF
// response envelope is tolerated (any 2xx counts as ok). Returns (ok, detail)
// where detail is the transport/HTTP error text for the journal on failure.
func SetStatus(base, token, scope, project, itemID, status, note string) (bool, string) {
	payload := map[string]string{
		"status": status,
		"note":   note,
	}
	if scope != "" {
		payload["scope"] = scope
	}
	if project != "" {
		payload["project"] = project
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return false, "marshal: " + err.Error()
	}
	u := strings.TrimRight(base, "/") + "/api/v1/backlog/items/" + itemID + "/status"
	req, err := http.NewRequest(http.MethodPost, u, bytes.NewReader(body))
	if err != nil {
		return false, err.Error()
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Roles", "operator")
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return false, err.Error()
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return false, "http " + http.StatusText(resp.StatusCode)
	}
	return true, ""
}
