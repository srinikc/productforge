package edpdata

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// RegenerateProjection writes a read-only JSONL projection from PostgreSQL.
func (s *EventStore) RegenerateProjection(ctx context.Context, tenant, path string) error {
	var events []Event
	var since int64
	for {
		page, maxSeq, err := s.Read(ctx, tenant, since, 1000)
		if err != nil {
			return err
		}
		events = append(events, page...)
		if len(page) < 1000 || maxSeq <= since {
			break
		}
		since = maxSeq
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	tmp := path + ".tmp"
	f, err := os.OpenFile(tmp, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	enc := json.NewEncoder(f)
	for _, ev := range events {
		row := map[string]any{
			"event_id": ev.EventID, "event_type": ev.Type, "event_version": ev.Version,
			"occurred_at": ev.OccurredAt.Format(time.RFC3339), "seq": ev.Seq,
			"tenant_id": ev.TenantID, "payload": ev.Payload,
			"projection": true, "projection_source": "postgres",
		}
		if err := enc.Encode(row); err != nil {
			_ = f.Close()
			_ = os.Remove(tmp)
			return err
		}
	}
	if err := f.Close(); err != nil {
		_ = os.Remove(tmp)
		return err
	}
	if err := os.Rename(tmp, path); err != nil {
		_ = os.Remove(tmp)
		return fmt.Errorf("event projection rename: %w", err)
	}
	return nil
}
