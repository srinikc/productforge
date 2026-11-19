package edpdata

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"productforge/datastore"
)

// ErrEventInvalid marks a malformed event append request.
var ErrEventInvalid = errors.New("edpdata: invalid event")

// Event is one persisted canonical event.
type Event struct {
	TenantID      string
	Seq           int64
	EventID       string
	OccurredAt    time.Time
	Type          string
	Version       string
	Payload       json.RawMessage
	PayloadRef    string
	PayloadSHA256 string
	SizeBytes     int64
	ContentType   string
	CorrelationID string
	CausationID   string
	Actor         string
}

// EventStore is the PostgreSQL event authority (single writer).
type EventStore struct {
	db          datastore.RelationalStore
	timeout     time.Duration
	payloads    PayloadStore
	inlineLimit int64
	outboxMax   int64
	metrics     EventMetrics
}

// NewEventStore returns an event store over db.
func NewEventStore(db datastore.RelationalStore) *EventStore {
	return &EventStore{db: db, timeout: defaultStatementTimeout, inlineLimit: 32 * 1024, outboxMax: 100_000, metrics: nopEventMetrics{}}
}

// WithOutboxBound configures pending-outbox backpressure.
func (s *EventStore) WithOutboxBound(maxPending int64) *EventStore {
	if maxPending > 0 {
		s.outboxMax = maxPending
	}
	return s
}

func (s *EventStore) setTenant(ctx context.Context, tx datastore.Tx, tenant string) error {
	if _, err := tx.Exec(ctx, "SELECT set_config('app.tenant_id', $1, true)", tenant); err != nil {
		return err
	}
	ms := s.timeout.Milliseconds()
	if ms <= 0 {
		ms = defaultStatementTimeout.Milliseconds()
	}
	_, err := tx.Exec(ctx, "SELECT set_config('statement_timeout', $1, true)", fmt.Sprintf("%dms", ms))
	return err
}

// WithPayloads configures object payload storage and the inline threshold.
func (s *EventStore) WithPayloads(store PayloadStore, inlineLimit int64) *EventStore {
	s.payloads = store
	if inlineLimit > 0 {
		s.inlineLimit = inlineLimit
	}
	return s
}

// Append stores one event and, when enabled, an atomic outbox row.
func (s *EventStore) Append(ctx context.Context, ev Event, outboxEnabled bool) (Event, error) {
	if ev.TenantID == "" || ev.EventID == "" || ev.Type == "" {
		return Event{}, fmt.Errorf("%w: tenant_id, event_id and type are required", ErrEventInvalid)
	}
	if ev.Version == "" {
		ev.Version = "1"
	}
	if len(ev.Payload) == 0 {
		ev.Payload = json.RawMessage(`{}`)
	}
	if s.inlineLimit > 0 && int64(len(ev.Payload)) > s.inlineLimit {
		if s.payloads == nil {
			return Event{}, fmt.Errorf("%w: object store required for payload", ErrEventInvalid)
		}
		ref, err := s.payloads.Put(ctx, ev.TenantID, ev.EventID, ev.Payload, ev.ContentType)
		if err != nil {
			return Event{}, err
		}
		ev.PayloadRef, ev.PayloadSHA256, ev.SizeBytes, ev.ContentType = ref.Ref, ref.SHA256, ref.Size, ref.ContentType
		ev.Payload = json.RawMessage(`{}`)
	}
	if outboxEnabled {
		if err := s.EnforceOutboxBound(ctx, ev.TenantID, s.outboxMax); err != nil {
			return Event{}, err
		}
	}
	var err error
	for attempt := 0; attempt < 5; attempt++ {
		err = s.db.WithTx(ctx, func(tx datastore.Tx) error {
			if err := s.setTenant(ctx, tx, ev.TenantID); err != nil {
				return err
			}
			var seq int64
			rows, err := tx.Query(ctx, "SELECT COALESCE(MAX(seq),0)+1 FROM events WHERE tenant_id=$1", ev.TenantID)
			if err != nil {
				return err
			}
			if rows.Next() {
				if err := rows.Scan(&seq); err != nil {
					rows.Close()
					return err
				}
			}
			if err := rows.Err(); err != nil {
				rows.Close()
				return err
			}
			_ = rows.Close()
			ev.Seq = seq
			if ev.OccurredAt.IsZero() {
				ev.OccurredAt = time.Now().UTC()
			}
			if _, err := tx.Exec(ctx, `INSERT INTO events
			(tenant_id,seq,event_id,occurred_at,type,version,payload,payload_ref,payload_sha256,size_bytes,content_type,correlation_id,causation_id,actor)
			VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11,$12,$13,$14)`,
				ev.TenantID, ev.Seq, ev.EventID, ev.OccurredAt, ev.Type, ev.Version, string(ev.Payload),
				ev.PayloadRef, ev.PayloadSHA256, ev.SizeBytes, ev.ContentType, ev.CorrelationID, ev.CausationID, ev.Actor); err != nil {
				return err
			}
			if outboxEnabled {
				if _, err := tx.Exec(ctx, `INSERT INTO events_outbox (id,tenant_id,event_id) VALUES ($1,$2,$3)`,
					fmt.Sprintf("%s-outbox", ev.EventID), ev.TenantID, ev.EventID); err != nil {
					return err
				}
			}
			return nil
		})
		if err == nil {
			break
		}
		if !strings.Contains(err.Error(), "events_pkey") && !strings.Contains(err.Error(), "events_tenant_id_seq_key") {
			break
		}
	}
	if err != nil {
		return Event{}, err
	}
	return ev, nil
}

// Read returns events with seq greater than sinceSeq for one tenant.
func (s *EventStore) Read(ctx context.Context, tenant string, sinceSeq int64, limit int) ([]Event, int64, error) {
	if tenant == "" {
		return nil, 0, fmt.Errorf("%w: tenant_id required", ErrEventInvalid)
	}
	if limit <= 0 || limit > 1000 {
		limit = 1000
	}
	var out []Event
	var maxSeq int64
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, tenant); err != nil {
			return err
		}
		rows, err := tx.Query(ctx, `SELECT tenant_id,seq,event_id,occurred_at,type,version,payload,payload_ref,payload_sha256,size_bytes,content_type,correlation_id,causation_id,actor
			FROM events WHERE tenant_id=$1 AND seq>$2 ORDER BY seq ASC LIMIT $3`, tenant, sinceSeq, limit)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var ev Event
			var payload []byte
			if err := rows.Scan(&ev.TenantID, &ev.Seq, &ev.EventID, &ev.OccurredAt, &ev.Type, &ev.Version, &payload,
				&ev.PayloadRef, &ev.PayloadSHA256, &ev.SizeBytes, &ev.ContentType, &ev.CorrelationID, &ev.CausationID, &ev.Actor); err != nil {
				return err
			}
			ev.Payload = json.RawMessage(payload)
			if ev.Seq > maxSeq {
				maxSeq = ev.Seq
			}
			out = append(out, ev)
		}
		return rows.Err()
	})
	return out, maxSeq, err
}
