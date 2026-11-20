package edpdata

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"productforge/datastore"
)

// Transport delivers one event. Implementations live outside this package.
type Transport interface {
	Deliver(ctx context.Context, sub Subscription, ev Event) error
}

// DispatchOptions bounds one dispatcher pass.
type DispatchOptions struct {
	Limit       int
	MaxAttempts int
	BaseBackoff time.Duration
	StaleAfter  time.Duration
	Now         func() time.Time
}

// DispatchStats reports one pass.
type DispatchStats struct {
	Delivered    int
	Skipped      int
	Retried      int
	DeadLettered int
}

type deliveryAction int

const (
	actionDeliver deliveryAction = iota
	actionSkip
	actionAdvance
)

func (o DispatchOptions) normalize() DispatchOptions {
	if o.Limit <= 0 {
		o.Limit = 100
	}
	if o.MaxAttempts <= 0 {
		o.MaxAttempts = 5
	}
	if o.BaseBackoff <= 0 {
		o.BaseBackoff = time.Second
	}
	if o.StaleAfter <= 0 {
		o.StaleAfter = 5 * time.Minute
	}
	if o.Now == nil {
		o.Now = time.Now
	}
	return o
}

func matchesFilter(sub Subscription, ev Event) bool {
	if len(sub.Filter) == 0 {
		return true
	}
	var payload map[string]any
	if err := json.Unmarshal(ev.Payload, &payload); err != nil {
		return false
	}
	for k, want := range sub.Filter {
		got, ok := payload[k]
		if !ok || fmt.Sprint(got) != want {
			return false
		}
	}
	return true
}

func matchesSubscription(sub Subscription, ev Event) bool {
	if len(sub.EventTypes) == 0 {
		return matchesFilter(sub, ev)
	}
	for _, t := range sub.EventTypes {
		if t == ev.Type {
			return matchesFilter(sub, ev)
		}
	}
	return false
}

func backoff(base time.Duration, attempts int) time.Duration {
	if attempts < 1 {
		attempts = 1
	}
	d := base
	for i := 1; i < attempts; i++ {
		d *= 2
		if d > time.Hour {
			return time.Hour
		}
	}
	return d
}

// DispatchOnce reads from the subscription cursor, dedupes by event_id and
// delivers matching events at-least-once. Cursor advancement and delivery rows
// commit together; a failed delivery stops the pass to preserve event order.
func (s *EventStore) DispatchOnce(ctx context.Context, sub Subscription, tr Transport,
	opts DispatchOptions) (DispatchStats, error) {
	opts = opts.normalize()
	var st DispatchStats
	events, _, err := s.Read(ctx, sub.TenantID, sub.LastSeq, opts.Limit)
	if err != nil {
		return st, err
	}
	for _, ev := range events {
		if !matchesSubscription(sub, ev) {
			if err := s.advanceCursor(ctx, sub, ev.Seq); err != nil {
				return st, err
			}
			st.Skipped++
			s.metrics.DeliverySkipped(sub.TenantID, sub.ID)
			continue
		}
		attempts, action, err := s.beginDelivery(ctx, sub, ev, opts)
		if err != nil {
			return st, err
		}
		switch action {
		case actionAdvance:
			if err := s.advanceCursor(ctx, sub, ev.Seq); err != nil {
				return st, err
			}
			st.Skipped++
			s.metrics.DeliverySkipped(sub.TenantID, sub.ID)
			continue
		case actionSkip:
			st.Skipped++
			s.metrics.DeliverySkipped(sub.TenantID, sub.ID)
			return st, nil
		}
		if err := tr.Deliver(ctx, sub, ev); err != nil {
			if attempts >= opts.MaxAttempts || IsPermanent(err) {
				if err := s.deadLetterDelivery(ctx, sub, ev, attempts, err.Error()); err != nil {
					return st, err
				}
				st.DeadLettered++
				s.metrics.DeliveryDeadLettered(sub.TenantID, sub.ID)
				continue
			}
			wait := backoff(opts.BaseBackoff, attempts)
			if ra, ok := err.(interface{ RetryAfter() time.Duration }); ok && ra.RetryAfter() > wait {
				wait = ra.RetryAfter()
			}
			if err := s.retryDelivery(ctx, sub, ev, attempts, opts.Now().Add(wait), err.Error()); err != nil {
				return st, err
			}
			st.Retried++
			s.metrics.DeliveryRetried(sub.TenantID, sub.ID)
			return st, nil
		}
		if err := s.completeDelivery(ctx, sub, ev, attempts); err != nil {
			return st, err
		}
		st.Delivered++
		s.metrics.DeliveryDelivered(sub.TenantID, sub.ID)
	}
	return st, nil
}

func (s *EventStore) advanceCursor(ctx context.Context, sub Subscription, seq int64) error {
	return s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, sub.TenantID); err != nil {
			return err
		}
		return advanceCursorTx(ctx, tx, sub, seq)
	})
}

func advanceCursorTx(ctx context.Context, tx datastore.Tx, sub Subscription, seq int64) error {
	_, err := tx.Exec(ctx, `UPDATE event_subscriptions SET last_seq=$2, updated_at=now()
		WHERE id=$1 AND tenant_id=$3 AND last_seq < $2`, sub.ID, seq, sub.TenantID)
	return err
}

func (s *EventStore) beginDelivery(ctx context.Context, sub Subscription, ev Event,
	opts DispatchOptions) (int, deliveryAction, error) {
	var attempts int
	action := actionDeliver
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, sub.TenantID); err != nil {
			return err
		}
		now := opts.Now()
		n, err := tx.Exec(ctx, `INSERT INTO event_deliveries
			(subscription_id,tenant_id,event_id,status,attempts,available_at,created_at,updated_at)
			VALUES ($1,$2,$3,'processing',1,$4::timestamptz,now(),now())
			ON CONFLICT (subscription_id,event_id) DO NOTHING`,
			sub.ID, sub.TenantID, ev.EventID, now)
		if err != nil {
			return err
		}
		if n > 0 {
			attempts = 1
			return nil
		}
		rows, err := tx.Query(ctx, `SELECT attempts,status,available_at,updated_at FROM event_deliveries
			WHERE subscription_id=$1 AND event_id=$2 FOR UPDATE`, sub.ID, ev.EventID)
		if err != nil {
			return err
		}
		defer rows.Close()
		if !rows.Next() {
			return fmt.Errorf("%w: delivery row missing after conflict", ErrEventInvalid)
		}
		var status string
		var availableAt, updatedAt time.Time
		if err := rows.Scan(&attempts, &status, &availableAt, &updatedAt); err != nil {
			return err
		}
		switch status {
		case "delivered", "failed":
			action = actionAdvance
		case "processing":
			if updatedAt.After(now.Add(-opts.StaleAfter)) {
				action = actionSkip
				return nil
			}
			attempts++
			action = actionDeliver
		case "retry":
			if availableAt.After(now) {
				action = actionSkip
				return nil
			}
			attempts++
			action = actionDeliver
		default:
			return fmt.Errorf("%w: unknown delivery status %q", ErrEventInvalid, status)
		}
		if action == actionDeliver {
			_, err = tx.Exec(ctx, `UPDATE event_deliveries
				SET attempts=$3,status='processing',updated_at=now()
				WHERE subscription_id=$1 AND event_id=$2`, sub.ID, ev.EventID, attempts)
		}
		return err
	})
	return attempts, action, err
}

func (s *EventStore) completeDelivery(ctx context.Context, sub Subscription, ev Event, attempts int) error {
	return s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, sub.TenantID); err != nil {
			return err
		}
		if _, err := tx.Exec(ctx, `UPDATE event_deliveries
			SET status='delivered',attempts=$3,last_error='',delivered_at=now(),updated_at=now()
			WHERE subscription_id=$1 AND event_id=$2`, sub.ID, ev.EventID, attempts); err != nil {
			return err
		}
		return advanceCursorTx(ctx, tx, sub, ev.Seq)
	})
}

func (s *EventStore) retryDelivery(ctx context.Context, sub Subscription, ev Event, attempts int, at time.Time, lastErr string) error {
	return s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, sub.TenantID); err != nil {
			return err
		}
		_, err := tx.Exec(ctx, `UPDATE event_deliveries SET status='retry',attempts=$3,available_at=$4::timestamptz,
			last_error=$5,updated_at=now() WHERE subscription_id=$1 AND event_id=$2`,
			sub.ID, ev.EventID, attempts, at, lastErr)
		return err
	})
}

func (s *EventStore) deadLetterDelivery(ctx context.Context, sub Subscription, ev Event, attempts int, lastErr string) error {
	return s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, sub.TenantID); err != nil {
			return err
		}
		if _, err := tx.Exec(ctx, `UPDATE event_deliveries SET status='failed',attempts=$3,
			last_error=$4,updated_at=now() WHERE subscription_id=$1 AND event_id=$2`,
			sub.ID, ev.EventID, attempts, lastErr); err != nil {
			return err
		}
		if _, err := tx.Exec(ctx, `INSERT INTO event_delivery_dlq
			(subscription_id,tenant_id,event_id,attempts,last_error) VALUES ($1,$2,$3,$4,$5)
			ON CONFLICT (subscription_id,event_id) DO UPDATE SET attempts=EXCLUDED.attempts,last_error=EXCLUDED.last_error`,
			sub.ID, sub.TenantID, ev.EventID, attempts, lastErr); err != nil {
			return err
		}
		return advanceCursorTx(ctx, tx, sub, ev.Seq)
	})
}
