// Command capsvc is the generic Go capability service (ADR-0007/0008).
//
// It exposes Go-backed, cross-cutting capabilities over a secured HTTP API and integrates with other
// services ONLY over HTTP (here: the backlog API, the single writer). First capability: doc-ingest.
//
// Env:
//
//	PF_CAP_ADDR     listen address (default 127.0.0.1:8020)
//	PF_CAP_TOKEN    required bearer token for inbound calls
//	PF_BACKLOG_API  backlog API base (default http://127.0.0.1:8010/api/v1)
//	PF_BACKLOG_TOKEN outbound token (default PF_CAP_TOKEN)
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"regexp"
	"strings"
	"time"

	"productforge/backlogctx"
)

type server struct {
	backlogAPI   string
	backlogToken string
	capToken     string
	client       *http.Client
}

var docRoute = regexp.MustCompile(`^/backlog/epics/(BI-PF-\d+)/context:from-doc$`)

func main() {
	s := &server{
		backlogAPI:   envOr("PF_BACKLOG_API", "http://127.0.0.1:8010/api/v1"),
		capToken:     os.Getenv("PF_CAP_TOKEN"),
		backlogToken: envOr("PF_BACKLOG_TOKEN", os.Getenv("PF_CAP_TOKEN")),
		client:       &http.Client{Timeout: 60 * time.Second},
	}
	if s.capToken == "" {
		log.Fatal("PF_CAP_TOKEN is required")
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) { _, _ = w.Write([]byte(`{"status":"ok"}`)) })
	mux.HandleFunc("/", s.route)
	addr := envOr("PF_CAP_ADDR", "127.0.0.1:8020")
	log.Printf("capsvc listening on %s (backlog=%s)", addr, s.backlogAPI)
	log.Fatal(http.ListenAndServe(addr, mux))
}

func envOr(k, d string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return d
}

func (s *server) route(w http.ResponseWriter, r *http.Request) {
	if m := docRoute.FindStringSubmatch(r.URL.Path); m != nil && r.Method == http.MethodPost {
		if !s.authorized(r) {
			http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
			return
		}
		s.contextFromDoc(w, r, m[1])
		return
	}
	http.Error(w, `{"error":"not found"}`, http.StatusNotFound)
}

func (s *server) authorized(r *http.Request) bool {
	auth := r.Header.Get("Authorization")
	return strings.TrimSpace(strings.TrimPrefix(auth, "Bearer ")) == s.capToken && strings.HasPrefix(auth, "Bearer ")
}

type docRequest struct {
	Doc        string `json:"doc"`
	SourceDoc  string `json:"source_doc"`
	Apply      bool   `json:"apply"`
	Overwrite  bool   `json:"overwrite"`
	Create     bool   `json:"create"`
	Scope      string `json:"scope"`
	Project    string `json:"project"`
}

func (s *server) contextFromDoc(w http.ResponseWriter, r *http.Request, epicID string) {
	var req docRequest
	if err := json.NewDecoder(io.LimitReader(r.Body, 5_000_000)).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid json body or too large"}`, http.StatusBadRequest)
		return
	}
	if strings.TrimSpace(req.Doc) == "" {
		http.Error(w, `{"error":"provide 'doc' text (binary formats: BI-PF-1403)"}`, http.StatusBadRequest)
		return
	}
	scope := req.Scope
	if scope == "" {
		scope = "product_forge"
	}
	sections := backlogctx.Parse(req.Doc)
	if len(sections) == 0 {
		http.Error(w, `{"error":"no item sections found"}`, http.StatusBadRequest)
		return
	}
	report := make([]map[string]any, 0, len(sections))
	for id, desired := range sections {
		cur, err := s.getItem(id, scope, req.Project)
		if err != nil {
			http.Error(w, fmt.Sprintf(`{"error":%q}`, err.Error()), http.StatusBadGateway)
			return
		}
		entry := map[string]any{"id": id, "state": "preview"}
		if cur == nil && !req.Create {
			entry["state"] = "not_found"
			report = append(report, entry)
			continue
		}
		if cur == nil {
			if !req.Apply {
				entry["state"] = "would_create"
				report = append(report, entry)
				continue
			}
			if cur, err = s.createItem(id, epicID, scope, req.Project); err != nil {
				http.Error(w, fmt.Sprintf(`{"error":%q}`, err.Error()), http.StatusBadGateway)
				return
			}
		}
		changed := backlogctx.Changes(cur, desired, req.Overwrite)
		if req.Apply && len(changed) > 0 {
			ctx, edit, deps := backlogctx.Route(changed)
			if err := s.apply(id, scope, req.Project, ctx, edit, deps); err != nil {
				entry["state"] = "error"
				entry["error"] = err.Error()
				report = append(report, entry)
				continue
			}
			entry["state"] = "applied"
		} else if req.Apply {
			entry["state"] = "unchanged"
		}
		keys := make([]string, 0, len(changed))
		for k := range changed {
			keys = append(keys, k)
		}
		entry["changed"] = keys
		report = append(report, entry)
	}
	writeJSON(w, http.StatusOK, map[string]any{"epic": epicID, "apply": req.Apply, "items": report})
}

func (s *server) call(method, path string, body any, out any) error {
	var rdr io.Reader
	if body != nil {
		b, _ := json.Marshal(body)
		rdr = bytes.NewReader(b)
	}
	req, err := http.NewRequest(method, s.backlogAPI+path, rdr)
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", "Bearer "+s.backlogToken)
	req.Header.Set("X-Roles", "operator")
	req.Header.Set("Content-Type", "application/json")
	resp, err := s.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(io.LimitReader(resp.Body, 5_000_000))
	if resp.StatusCode >= 400 {
		return fmt.Errorf("%s %s -> %d: %s", method, path, resp.StatusCode, strings.TrimSpace(string(data)))
	}
	if out != nil {
		return json.Unmarshal(data, out)
	}
	return nil
}

func (s *server) getItem(id, scope, project string) (map[string]any, error) {
	var env struct {
		Data map[string]any `json:"data"`
	}
	err := s.call(http.MethodGet, fmt.Sprintf("/backlog/items/%s?scope=%s&project=%s", id, scope, project), nil, &env)
	if err != nil {
		if strings.Contains(err.Error(), "-> 404") {
			return nil, nil
		}
		return nil, err
	}
	return env.Data, nil
}

func (s *server) createItem(id, epic, scope, project string) (map[string]any, error) {
	var env struct {
		Data map[string]any `json:"data"`
	}
	err := s.call(http.MethodPost, "/backlog/items", map[string]any{
		"title": id, "type": "feature", "epic": epic, "external_id": id, "scope": scope, "project": project,
	}, &env)
	return env.Data, err
}

func (s *server) apply(id, scope, project string, ctx, edit, deps map[string]any) error {
	if len(ctx) > 0 {
		ctx["scope"] = scope
		ctx["project"] = project
		if err := s.call(http.MethodPost, "/backlog/items/"+id+"/context", ctx, nil); err != nil {
			return err
		}
	}
	if len(edit) > 0 {
		edit["scope"] = scope
		edit["project"] = project
		if err := s.call(http.MethodPatch, "/backlog/items/"+id, edit, nil); err != nil {
			return err
		}
	}
	if len(deps) > 0 {
		deps["scope"] = scope
		deps["project"] = project
		if err := s.call(http.MethodPost, "/backlog/items/"+id+"/dependencies", deps, nil); err != nil {
			return err
		}
	}
	return nil
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}
