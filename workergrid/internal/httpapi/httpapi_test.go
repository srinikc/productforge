package httpapi

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"workergrid/internal/store"
)

// newTest spins the handler with an isolated temp state dir and a fixed token
// (config.json is neutralized via an empty WORKERGRID_HOME).
func newTest(t *testing.T) (http.Handler, string) {
	t.Helper()
	t.Setenv("WORKERGRID_HOME", t.TempDir())
	t.Setenv("WORKERGRID_STATE_DIR", t.TempDir())
	t.Setenv("WORKERGRID_TOKEN", "sekrit")
	t.Setenv("API_TOKEN", "")
	st, err := store.Open(t.TempDir(), func() int { return 3600 })
	if err != nil {
		t.Fatalf("store: %v", err)
	}
	t.Cleanup(func() { _ = st.Close() })
	return Handler(st), "Bearer sekrit"
}

func do(h http.Handler, method, path, body, token string) *httptest.ResponseRecorder {
	var rdr *bytes.Reader
	if body == "" {
		rdr = bytes.NewReader(nil)
	} else {
		rdr = bytes.NewReader([]byte(body))
	}
	req := httptest.NewRequest(method, path, rdr)
	if token != "" {
		req.Header.Set("Authorization", token)
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func TestAuthPrecedenceAndStatus(t *testing.T) {
	h, tok := newTest(t)
	if rec := do(h, "GET", "/status", "", ""); rec.Code != 401 ||
		!strings.Contains(rec.Body.String(), "unauthorized") {
		t.Fatalf("no token -> 401: %d %s", rec.Code, rec.Body.String())
	}
	if rec := do(h, "GET", "/status", "", "Bearer wrong"); rec.Code != 401 {
		t.Fatalf("wrong token -> 401: %d", rec.Code)
	}
	// auth runs before routing: bad token on an unknown path is still 401
	if rec := do(h, "GET", "/nope", "", "Bearer wrong"); rec.Code != 401 {
		t.Fatalf("bad token on unknown path -> 401: %d", rec.Code)
	}
	rec := do(h, "GET", "/status", "", tok)
	if rec.Code != 200 || !strings.Contains(rec.Body.String(), `"producer"`) {
		t.Fatalf("status: %d %s", rec.Code, rec.Body.String())
	}
	if rec := do(h, "GET", "/nope", "", tok); rec.Code != 404 ||
		!strings.Contains(rec.Body.String(), "not found") {
		t.Fatalf("404: %d %s", rec.Code, rec.Body.String())
	}
	if rec := do(h, "PUT", "/status", "", tok); rec.Code != 501 {
		t.Fatalf("unsupported method -> 501: %d", rec.Code)
	}
}

func TestRegisterGetHeartbeatFlow(t *testing.T) {
	h, tok := newTest(t)
	body := `{"worker_id":"WRK-u1","runtime":"opencode","capabilities":["python"],"role":"dev"}`
	rec := do(h, "POST", "/workers/register", body, tok)
	if rec.Code != 200 || !strings.Contains(rec.Body.String(), `"status":"ONLINE"`) ||
		!strings.Contains(rec.Body.String(), `"capabilities":"python"`) {
		t.Fatalf("register: %d %s", rec.Code, rec.Body.String())
	}
	if rec = do(h, "GET", "/workers/WRK-u1", "", tok); rec.Code != 200 {
		t.Fatalf("get worker: %d %s", rec.Code, rec.Body.String())
	}
	if rec = do(h, "GET", "/workers/unknown", "", tok); rec.Code != 404 {
		t.Fatalf("unknown worker -> 404: %d", rec.Code)
	}
	if rec = do(h, "POST", "/workers/WRK-u1/heartbeat",
		`{"status":"IDLE","current_assignment":""}`, tok); rec.Code != 200 ||
		!strings.Contains(rec.Body.String(), `"ok":true`) {
		t.Fatalf("heartbeat: %d %s", rec.Code, rec.Body.String())
	}
	if rec = do(h, "POST", "/workers/nope/heartbeat", `{}`, tok); rec.Code != 200 ||
		!strings.Contains(rec.Body.String(), `"ok":false`) {
		t.Fatalf("unknown heartbeat stays 200/ok=false: %d %s", rec.Code, rec.Body.String())
	}
}

func TestMalformedBodyTreatedAsEmpty(t *testing.T) {
	h, tok := newTest(t)
	rec := do(h, "POST", "/workers/register", "not-json{", tok)
	// python: invalid JSON -> {} -> generated id
	if rec.Code != 200 || !strings.Contains(rec.Body.String(), `"worker_id":"WRK-`) {
		t.Fatalf("malformed register: %d %s", rec.Code, rec.Body.String())
	}
}
