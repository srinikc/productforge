// Package httpapi is the WorkerGrid coordinator HTTP surface - the Go port of
// workergrid/service.py (BI-PF-0412). Routing, auth precedence, JSON shapes and
// status codes mirror the Python spike exactly; the cross-impl contract suite
// (test-framework/tests/pipeline/test_workergrid_service_contract.py) is the
// parity proof.
package httpapi

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strings"

	"workergrid/internal/config"
	"workergrid/internal/producer"
	"workergrid/internal/store"
)

var (
	reWorker  = regexp.MustCompile(`^/workers/([^/]+)$`)
	reBeat    = regexp.MustCompile(`^/workers/([^/]+)/heartbeat$`)
	reUnreg   = regexp.MustCompile(`^/workers/([^/]+)/unregister$`)
	reRenew   = regexp.MustCompile(`^/leases/([^/]+)/renew$`)
	reRelease = regexp.MustCompile(`^/leases/([^/]+)/release$`)
)

// Handler serves the coordinator API over st (single writer: this process).
func Handler(st *store.Store) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		cfg := config.Load()
		tok := strings.TrimSpace(cfg.Token())
		if tok != "" && r.Header.Get("Authorization") != "Bearer "+tok {
			writeJSON(w, 401, map[string]any{"error": "unauthorized"})
			return
		}
		method := r.Method
		if method != http.MethodGet && method != http.MethodPost {
			// Python's BaseHTTPRequestHandler: unimplemented method -> 501.
			writeJSON(w, 501, map[string]any{"error": "unsupported method"})
			return
		}
		body := map[string]any{}
		if method == http.MethodPost {
			body = readBody(r)
		}
		p := r.URL.Path

		switch {
		case p == "/status" && method == http.MethodGet:
			nw, nl, err := st.Count()
			if err != nil {
				writeErr(w, err)
				return
			}
			writeJSON(w, 200, map[string]any{
				"workers": nw, "leases": nl, "producer": cfg.ProducerBase(),
			})
		case p == "/workers" && method == http.MethodGet:
			ws, err := st.ListWorkers()
			if err != nil {
				writeErr(w, err)
				return
			}
			writeJSON(w, 200, map[string]any{"workers": ws})
		case p == "/workers/register" && method == http.MethodPost:
			wkr, err := st.Register(asString(body["worker_id"]),
				asString(body["runtime"]), capsList(body["capabilities"]),
				asString(body["role"]))
			if err != nil {
				writeErr(w, err)
				return
			}
			writeJSON(w, 200, wkr)
		case reWorker.MatchString(p) && method == http.MethodGet:
			wkr, err := st.Get(reWorker.FindStringSubmatch(p)[1])
			if err != nil {
				writeErr(w, err)
				return
			}
			if wkr == nil {
				writeJSON(w, 404, map[string]any{"error": "not found"})
				return
			}
			writeJSON(w, 200, wkr)
		case reBeat.MatchString(p) && method == http.MethodPost:
			res, err := st.Heartbeat(reBeat.FindStringSubmatch(p)[1],
				asString(body["status"]), asString(body["current_assignment"]))
			if err != nil {
				writeErr(w, err)
				return
			}
			writeJSON(w, 200, res)
		case reUnreg.MatchString(p) && method == http.MethodPost:
			res, err := st.Unregister(reUnreg.FindStringSubmatch(p)[1])
			if err != nil {
				writeErr(w, err)
				return
			}
			writeJSON(w, 200, res)
		case p == "/work" && method == http.MethodPost:
			res, err := assign(st, cfg, body)
			if err != nil {
				writeErr(w, err)
				return
			}
			writeJSON(w, 200, res)
		case reRenew.MatchString(p) && method == http.MethodPost:
			res, err := st.Renew(reRenew.FindStringSubmatch(p)[1])
			if err != nil {
				writeErr(w, err)
				return
			}
			writeJSON(w, 200, res)
		case reRelease.MatchString(p) && method == http.MethodPost:
			res, err := st.Release(reRelease.FindStringSubmatch(p)[1])
			if err != nil {
				writeErr(w, err)
				return
			}
			writeJSON(w, 200, res)
		case p == "/leases/recover" && method == http.MethodPost:
			res, err := st.RecoverExpired()
			if err != nil {
				writeErr(w, err)
				return
			}
			writeJSON(w, 200, res)
		default:
			writeJSON(w, 404, map[string]any{"error": "not found"})
		}
	})
}

// assign claims the next eligible item for a registered worker (Python _assign).
func assign(st *store.Store, cfg config.Config, body map[string]any) (map[string]any, error) {
	wid := asString(body["worker_id"])
	if wid == "" {
		return map[string]any{"assigned": false, "reason": "worker not registered"}, nil
	}
	w, err := st.Get(wid)
	if err != nil {
		return nil, err
	}
	if w == nil {
		return map[string]any{"assigned": false, "reason": "worker not registered"}, nil
	}
	scope := asString(body["scope"])
	if scope == "" {
		scope = "product_forge"
	}
	data, ok := producer.Next(cfg.ProducerBase(), cfg.Token(), scope, asString(body["project"]))
	if data == nil {
		data = map[string]any{}
	}
	// BI-PF-0412 (RCCA): the producer wraps the payload in its canonical
	// envelope {request_id, status, data:{found, item, ...}} - unwrap one
	// level before reading (mirror of service.py).
	if _, has := data["found"]; !has {
		if inner, isMap := data["data"].(map[string]any); isMap {
			data = inner
		}
	}
	item := data["item"]
	if !ok || !truthy(data["found"]) || !truthy(item) {
		return map[string]any{"assigned": false, "reason": "no eligible work"}, nil
	}
	itemStr := asString(item)
	lease, err := st.Claim(itemStr, wid, asString(body["runtime"]))
	if err != nil {
		return nil, err
	}
	if !truthy(lease["claimed"]) {
		reason, _ := lease["reason"].(string)
		if reason == "" {
			reason = "lease denied"
		}
		return map[string]any{"assigned": false, "reason": reason}, nil
	}
	out := map[string]any{
		"assigned": true, "item_id": itemStr, "title": data["title"],
		"worker_id": wid, "assignment_id": lease["assignment_id"],
		"expires_at": lease["expires_at"],
	}
	// pickup contract from the producer (optional): what the worker carries (ADR-0002)
	for _, k := range []string{"pidl_context", "execution_policy"} {
		if data[k] != nil {
			out[k] = data[k]
		}
	}
	return out, nil
}

// readBody mirrors service.py::_body: absent/short/invalid JSON -> {}.
func readBody(r *http.Request) map[string]any {
	if r.ContentLength == 0 {
		return map[string]any{}
	}
	raw, err := io.ReadAll(io.LimitReader(r.Body, 4<<20))
	if err != nil || len(raw) == 0 {
		return map[string]any{}
	}
	var v any
	if err := json.Unmarshal(raw, &v); err != nil {
		return map[string]any{}
	}
	if m, ok := v.(map[string]any); ok && m != nil {
		return m
	}
	return map[string]any{}
}

// asString mirrors Python's str(x or "") for the scalar JSON types we accept.
func asString(v any) string {
	switch t := v.(type) {
	case nil:
		return ""
	case string:
		return t
	case bool:
		if t {
			return "True"
		}
		return "False"
	case float64:
		if t == float64(int64(t)) {
			return fmt.Sprintf("%d", int64(t))
		}
		return fmt.Sprintf("%v", t)
	default:
		return fmt.Sprintf("%v", t)
	}
}

// capsList mirrors `body.get("capabilities") or []` + ",".join(str(c)): a JSON
// array is joined element-wise; a bare string joins its characters; other
// truthy scalars stringify as one element (Python str()); falsy -> empty.
func capsList(v any) []string {
	if !truthy(v) {
		return nil
	}
	switch t := v.(type) {
	case []any:
		out := make([]string, 0, len(t))
		for _, e := range t {
			out = append(out, asString(e))
		}
		return out
	case string:
		out := make([]string, 0, len(t))
		for _, ch := range t {
			out = append(out, string(ch))
		}
		return out
	default:
		return []string{asString(v)}
	}
}

// truthy mirrors Python's bool(x) for JSON values.
func truthy(v any) bool {
	switch t := v.(type) {
	case nil:
		return false
	case bool:
		return t
	case string:
		return t != ""
	case float64:
		return t != 0
	case []any:
		return len(t) > 0
	case map[string]any:
		return len(t) > 0
	default:
		return true
	}
}

func writeJSON(w http.ResponseWriter, code int, obj any) {
	body, err := json.Marshal(obj)
	if err != nil {
		body = []byte(`{"error":"marshal failed"}`)
		code = 500
	}
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Content-Length", fmt.Sprintf("%d", len(body)))
	w.WriteHeader(code)
	_, _ = w.Write(body)
}

func writeErr(w http.ResponseWriter, err error) {
	writeJSON(w, 500, map[string]any{"error": err.Error()})
}
