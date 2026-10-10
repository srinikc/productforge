// Package producer asks Product Forge's scheduling API for the next eligible
// work item - the Go port of workergrid/client.py (BI-PF-0412).
package producer

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

// Next fetches the next eligible item from
// GET {base}/api/v1/engineering/schedule/next?scope=&project=&stage=&epic=.
// `stage="execute"` (BI-PF-0416) asks the producer for NOT-yet-executed work only, so the
// coordinator cannot re-claim an item already executed (`implemented`/`verifying`).
// `epic` (BI-PF-1222) restricts the pick to that epic's children ("" = whole backlog).
// Returns (data, ok): ok=false on transport/non-2xx errors (service then
// reports "no eligible work", matching the Python spike); data is the parsed
// JSON body (map) or nil when the producer answers non-JSON.
func Next(base, token, scope, project, stage, epic string) (map[string]any, bool) {
	q := url.Values{}
	if scope != "" {
		q.Set("scope", scope)
	}
	if project != "" {
		q.Set("project", project)
	}
	if stage != "" {
		q.Set("stage", stage)
	}
	if epic != "" {
		q.Set("epic", epic)
	}
	u := base + "/api/v1/engineering/schedule/next"
	if len(q) > 0 {
		u += "?" + q.Encode()
	}
	req, err := http.NewRequest(http.MethodGet, u, nil)
	if err != nil {
		return nil, false
	}
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, false
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, false
	}
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
	if err != nil {
		return nil, false
	}
	var data map[string]any
	if err := json.Unmarshal(raw, &data); err != nil {
		return nil, true
	}
	return data, true
}

// Errf is a small helper kept for parity with client.py's error strings.
func Errf(format string, args ...any) error {
	return fmt.Errorf(format, args...)
}
