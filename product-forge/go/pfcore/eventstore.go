// eventstore.go is the PF native Go event core (BI-PF-1268; ADR-0005): an append-only
// store with a monotonic per-store `seq` and cursor reads. It speaks the A1 wire contract
// (ops event_append / event_read) and is invoked from the PF runtime via core/go_host.
//
// Single writer: appends take a portable exclusive lock (O_CREATE|O_EXCL lock file beside
// the store), mirroring the Python lock pattern in core/worker.py. Stdlib only.
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"productforge/edpdata"
)

// lockEventStore acquires a portable exclusive lock beside path (never blocks forever).
func lockEventStore(path string) (string, error) {
	lp := path + ".lock"
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return "", err
	}
	for i := 0; i < 50; i++ {
		f, err := os.OpenFile(lp, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
		if err == nil {
			_ = f.Close()
			return lp, nil
		}
		// stale lock (crashed writer): break it after 5 minutes
		if fi, statErr := os.Stat(lp); statErr == nil && time.Since(fi.ModTime()) > 300*time.Second {
			_ = os.Remove(lp)
			continue
		}
		time.Sleep(100 * time.Millisecond)
	}
	return "", errors.New("could not acquire event-store lock")
}

func unlockEventStore(lp string) { _ = os.Remove(lp) }

// lastSeq returns the highest `seq` currently persisted (0 if none/absent).
func lastSeq(path string) (int64, error) {
	f, err := os.Open(path)
	if err != nil {
		if os.IsNotExist(err) {
			return 0, nil
		}
		return 0, err
	}
	defer f.Close()
	var last int64
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 64*1024), 4*1024*1024)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		var ev map[string]any
		if json.Unmarshal([]byte(line), &ev) != nil {
			continue
		}
		if v, ok := ev["seq"].(float64); ok && int64(v) > last {
			last = int64(v)
		}
	}
	return last, sc.Err()
}

// AppendEvent assigns a monotonic seq under the lock and appends one JSON line.
func AppendEvent(path string, event map[string]any) (map[string]any, error) {
	if event == nil {
		return nil, errors.New("event must be an object")
	}
	lp, err := lockEventStore(path)
	if err != nil {
		return nil, err
	}
	defer unlockEventStore(lp)
	last, err := lastSeq(path)
	if err != nil {
		return nil, err
	}
	seq := last + 1
	event["seq"] = seq
	line, err := json.Marshal(event)
	if err != nil {
		return nil, err
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return nil, err
	}
	if _, err = f.Write(append(line, '\n')); err != nil {
		_ = f.Close()
		return nil, err
	}
	return map[string]any{"seq": seq, "record": event}, f.Close()
}

// ReadEvents returns events with seq > sinceSeq (up to limit; 0 = all) plus the max seq seen.
func ReadEvents(path string, sinceSeq int64, limit int) ([]map[string]any, int64, error) {
	f, err := os.Open(path)
	if err != nil {
		if os.IsNotExist(err) {
			return []map[string]any{}, 0, nil
		}
		return nil, 0, err
	}
	defer f.Close()
	out := []map[string]any{}
	var maxSeq int64
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 64*1024), 4*1024*1024)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		var ev map[string]any
		if json.Unmarshal([]byte(line), &ev) != nil {
			continue
		}
		seq := int64(0)
		if v, ok := ev["seq"].(float64); ok {
			seq = int64(v)
		}
		if seq > maxSeq {
			maxSeq = seq
		}
		if seq > sinceSeq {
			out = append(out, ev)
			if limit > 0 && len(out) >= limit {
				break
			}
		}
	}
	if err := sc.Err(); err != nil {
		return nil, 0, err
	}
	return out, maxSeq, nil
}

func asInt64(v any) (int64, bool) {
	switch n := v.(type) {
	case float64:
		return int64(n), true
	case int:
		return int64(n), true
	case int64:
		return n, true
	case string:
		if p, err := strconv.ParseInt(strings.TrimSpace(n), 10, 64); err == nil {
			return p, true
		}
	}
	return 0, false
}

// EventAppendOp handles the event_append wire op; returns (result, error-message).
var (
	eventStoreMu sync.Mutex
	eventStore   *edpdata.EventStore
)

func sharedEventStore(ctx context.Context) (*edpdata.EventStore, error) {
	eventStoreMu.Lock()
	defer eventStoreMu.Unlock()
	if eventStore != nil {
		return eventStore, nil
	}
	st, _, err := edpdata.OpenEventStoreFromEnv(ctx)
	if err != nil {
		return nil, err
	}
	eventStore = st
	return st, nil
}

func outboxEnabled() (bool, error) {
	v := strings.ToLower(strings.TrimSpace(os.Getenv("EVENT_OUTBOX_ENABLED")))
	switch v {
	case "", "off", "0", "false", "no":
		return false, nil
	case "on", "1", "true", "yes":
		return true, nil
	default:
		return false, fmt.Errorf("invalid EVENT_OUTBOX_ENABLED=%q", v)
	}
}

func projectionPath(tenant string) string {
	if root := os.Getenv("PF_EVENT_PROJECTION_DIR"); root != "" {
		return filepath.Join(root, tenant, "events.jsonl")
	}
	return filepath.Join("products", tenant, "events.jsonl")
}

func EventAppendOp(payload map[string]any) (map[string]any, string) {
	ev, ok := payload["event"].(map[string]any)
	if !ok {
		return nil, "event_append: payload.event must be an object"
	}
	if os.Getenv("PF_DB_DSN") != "" {
		tenant, _ := payload["tenant_id"].(string)
		if tenant == "" {
			tenant, _ = ev["tenant_id"].(string)
		}
		if tenant == "" {
			return nil, "event_append: tenant_id is required for the PostgreSQL event authority"
		}
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		st, err := sharedEventStore(ctx)
		if err != nil {
			return nil, fmt.Sprintf("event_append: %v", err)
		}
		outbox, err := outboxEnabled()
		if err != nil {
			return nil, fmt.Sprintf("event_append: %v", err)
		}
		eventID, _ := ev["event_id"].(string)
		eventType, _ := ev["event_type"].(string)
		if eventID == "" || eventType == "" {
			return nil, "event_append: event_id and event_type are required"
		}
		recorded, err := st.Append(ctx, edpdata.Event{
			TenantID: tenant, EventID: eventID, Type: eventType,
			Version: fmt.Sprint(ev["event_version"]), Payload: mustJSON(ev["payload"]),
			CorrelationID: fmt.Sprint(ev["correlation_id"]), CausationID: fmt.Sprint(ev["causation_id"]),
			Actor: fmt.Sprint(ev["actor"]),
		}, outbox)
		if err != nil {
			return nil, fmt.Sprintf("event_append: %v", err)
		}
		ev["seq"] = recorded.Seq
		projPath := projectionPath(tenant)
		result := map[string]any{"seq": recorded.Seq, "record": ev}
		if err := st.RegenerateProjection(ctx, tenant, projPath); err != nil {
			result["projection_error"] = err.Error()
		}
		return result, ""
	}
	path, _ := payload["path"].(string)
	if strings.TrimSpace(path) == "" {
		return nil, "event_append: payload.path is required in legacy JSONL mode"
	}
	res, err := AppendEvent(path, ev)
	if err != nil {
		return nil, fmt.Sprintf("event_append: %v", err)
	}
	return res, ""
}

// EventReadOp handles the event_read wire op; returns (result, error-message).
func EventReadOp(payload map[string]any) (map[string]any, string) {
	var since int64
	if v, ok := payload["since_seq"]; ok {
		since, _ = asInt64(v)
	}
	limit := 0
	if v, ok := payload["limit"]; ok {
		if n, ok := asInt64(v); ok {
			limit = int(n)
		}
	}
	if os.Getenv("PF_DB_DSN") != "" {
		tenant, _ := payload["tenant_id"].(string)
		if tenant == "" {
			return nil, "event_read: tenant_id is required for the PostgreSQL event authority"
		}
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		st, err := sharedEventStore(ctx)
		if err != nil {
			return nil, fmt.Sprintf("event_read: %v", err)
		}
		rows, maxSeq, err := st.Read(ctx, tenant, since, limit)
		if err != nil {
			return nil, fmt.Sprintf("event_read: %v", err)
		}
		events := make([]map[string]any, 0, len(rows))
		for _, r := range rows {
			events = append(events, map[string]any{"seq": r.Seq, "event_id": r.EventID, "event_type": r.Type, "event_version": r.Version, "tenant_id": r.TenantID, "payload": json.RawMessage(r.Payload)})
		}
		return map[string]any{"events": events, "count": len(events), "max_seq": maxSeq}, ""
	}
	path, _ := payload["path"].(string)
	if strings.TrimSpace(path) == "" {
		return nil, "event_read: payload.path is required in legacy JSONL mode"
	}
	events, maxSeq, err := ReadEvents(path, since, limit)
	if err != nil {
		return nil, fmt.Sprintf("event_read: %v", err)
	}
	return map[string]any{"events": events, "count": len(events), "max_seq": maxSeq}, ""
}

func mustJSON(v any) json.RawMessage {
	b, _ := json.Marshal(v)
	return json.RawMessage(b)
}
