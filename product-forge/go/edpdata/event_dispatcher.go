package edpdata

import (
	"context"
	"time"

	"productforge/datastore"
)

// Transport delivers one event. Implementations live outside this package (BI-PF-1270).
type Transport interface {
	Deliver(ctx context.Context, sub Subscription, ev Event) error
}

// DispatchOptions bounds one dispatcher pass.
type DispatchOptions struct {
	Limit       int
	MaxAttempts int
	BaseBackoff time.Duration
	Now         func() time.Time
}

// DispatchStats reports one pass.
type DispatchStats struct {
	Delivered    int
	Skipped      int
	Retried      int
	DeadLettered int
}

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
	if o.Now == nil {
		o.Now = time.Now
	}
	return o
}

func matchesSubscription(sub Subscription, ev Event) bool {
	if len(sub.EventTypes) == 0 {
		return true
	}
	for _, t := range sub.EventTypes {
		if t == ev.Type {
			return true
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
// delivers matching events at-least-once. Failures retry, then move to DLQ.
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
			continue
		}
		attempts, duplicate, err := s.beginDelivery(ctx, sub, ev, opts.Now())
		if err != nil {
			return st, err
		}
		if duplicate {
			st.Skipped++
			continue
		}
		sendErr := tr.Deliver(ctx, sub, ev)
		if sendErr == nil {
			if err := s.finishDelivery(ctx, sub, ev, true, attempts, ""); err != nil {
				return st, err
			}
			st.Delivered++
			continue
		}
		if attempts >= opts.MaxAttempts {
			if err := s.finishDelivery(ctx, sub, ev, false, attempts, sendErr.Error()); err != nil {
				return st, err
			}
			if err := s.dlq(ctx, sub, ev, attempts, sendErr.Error()); err != nil {
				return st, err
			}
			st.DeadLettered++
			continue
		}
		if err := s.retryDelivery(ctx, sub, ev, attempts, opts.Now().Add(backoff(opts.BaseBackoff, attempts)), sendErr.Error()); err != nil {
			return st, err
		}
		st.Retried++
		return st, nil
	}
	return st, nil
}

func (s *EventStore) advanceCursor(ctx context.Context, sub Subscription, seq int64) error {
	return s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, sub.TenantID); err != nil {
			return err
		}
		_, err := tx.Exec(ctx, `UPDATE event_subscriptions SET last_seq=$2, updated_at=now()
			WHERE id=$1 AND tenant_id=$3 AND last_seq < $2`, sub.ID, seq, sub.TenantID)
		return err
	})
}

func (s *EventStore) beginDelivery(ctx context.Context, sub Subscription, ev Event, now time.Time) (int, bool, error) {
	var attempts int
	duplicate := false
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, sub.TenantID); err != nil {
			return err
		}
		n, err := tx.Exec(ctx, `INSERT INTO event_deliveries
			(subscription_id,tenant_id,event_id,status,attempts,available_at,updated_at)
			VALUES ($1,$2,$3,'processing',1,$4,now())
			ON CONFLICT (subscription_id,event_id) DO NOTHING`,
			sub.ID, sub.TenantID, ev.EventID, now)
		if err != nil {
			return err
		}
		if n > 0 {
			attempts = 1
			return nil
		}
		duplicate = true
		rows, err := tx.Query(ctx, `SELECT attempts,status FROM event_deliveries
			WHERE subscription_id=$1 AND event_id=$2`, sub.ID, ev.EventID)
		if err != nil {
			return err
		}
		defer rows.Close()
		if rows.Next() {
			var status string
			if err := rows.Scan(&attempts, &status); err != nil {
				return err
			}
			duplicate = status == "delivered" || status == "failed"
			if !duplicate {
				attempts++
				_, err = tx.Exec(ctx, `UPDATE event_deliveries SET attempts=$3,status='processing',updated_at=now()
					WHERE subscription_id=$1 AND event_id=$2`, sub.ID, ev.EventID, attempts)
			}
		}
		return err
	})
	return attempts, duplicate, err
}

func (s *EventStore) finishDelivery(ctx context.Context, sub Subscription, ev Event, ok bool, attempts int, lastErr string) error {
	return s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, sub.TenantID); err != nil {
			return err
		}
		status, delivered := "failed", "failed"
		if ok {
			status, delivered = "delivered", "delivered"
		}
		if _, err := tx.Exec(ctx, `UPDATE event_deliveries SET status=$3,attempts=$4,last_error=$5,
			delivered_at=CASE WHEN $3='delivered' THEN now() ELSE delivered_at END, updated_at=now()
			WHERE subscription_id=$1 AND event_id=$2`, sub.ID, ev.EventID, status, attempts, lastErr); err != nil {
			return err
		}
		if delivered == "delivered" {
			_, err := tx.Exec(ctx, `UPDATE event_subscriptions SET last_seq=$2,updated_at=now()
				WHERE id=$1 AND tenant_id=$3 AND last_seq < $2`, sub.ID, ev.Seq, sub.TenantID)
			return err
		}
		return nil
	})
}

func (s *EventStore) retryDelivery(ctx context.Context, sub Subscription, ev Event, attempts int, at time.Time, lastErr string) error {
	return s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, sub.TenantID); err != nil {
			return err
		}
		_, err := tx.Exec(ctx, `UPDATE event_deliveries SET status='retry',attempts=$3,available_at=$4,
			last_error=$5,updated_at=now() WHERE subscription_id=$1 AND event_id=$2`,
			sub.ID, ev.EventID, attempts, at, lastErr)
		return err
	})
}

func (s *EventStore) dlq(ctx context.Context, sub Subscription, ev Event, attempts int, lastErr string) error {
	return s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, sub.TenantID); err != nil {
			return err
		}
		if _, err := tx.Exec(ctx, `INSERT INTO event_delivery_dlq
			(subscription_id,tenant_id,event_id,attempts,last_error) VALUES ($1,$2,$3,$4,$5)
			ON CONFLICT (subscription_id,event_id) DO UPDATE SET attempts=EXCLUDED.attempts,last_error=EXCLUDED.last_error`,
			sub.ID, sub.TenantID, ev.EventID, attempts, lastErr); err != nil {
			return err
		}
		_, err := tx.Exec(ctx, `UPDATE event_subscriptions SET last_seq=$2,updated_at=now()
			WHERE id=$1 AND tenant_id=$3 AND last_seq < $2`, sub.ID, ev.Seq, sub.TenantID)
		return err
	})
}
