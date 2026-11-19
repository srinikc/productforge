package edpdata

import (
	"context"
	"errors"
	"fmt"
	"os"
	"testing"
	"time"
)

type funcTransport func(context.Context, Subscription, Event) error

func (f funcTransport) Deliver(ctx context.Context, sub Subscription, ev Event) error {
	return f(ctx, sub, ev)
}

func TestDispatcherPostgresIntegration(t *testing.T) {
	if os.Getenv("PF_DB_DSN") == "" {
		t.Skip("PF_DB_DSN not set - skipping dispatcher integration test")
	}
	ctx := context.Background()
	st, closeFn, err := OpenEventStoreFromEnv(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer closeFn()

	tenant := fmt.Sprintf("dispatch-%d", time.Now().UnixNano())
	ev, err := st.Append(ctx, Event{TenantID: tenant, EventID: tenant + "-e1", Type: "run_started"}, false)
	if err != nil {
		t.Fatal(err)
	}

	okSub := Subscription{ID: tenant + "-ok", TenantID: tenant, EventTypes: []string{"run_started"}, Transport: "func", Enabled: true}
	if err := st.UpsertSubscription(ctx, okSub); err != nil {
		t.Fatal(err)
	}
	sent := 0
	res, err := st.DispatchOnce(ctx, okSub, funcTransport(func(context.Context, Subscription, Event) error {
		sent++
		return nil
	}), DispatchOptions{MaxAttempts: 3})
	if err != nil {
		t.Fatal(err)
	}
	if res.Delivered != 1 || sent != 1 {
		t.Fatalf("delivered=%d sent=%d", res.Delivered, sent)
	}

	okSub.LastSeq = ev.Seq
	res, err = st.DispatchOnce(ctx, okSub, funcTransport(func(context.Context, Subscription, Event) error {
		t.Fatal("duplicate event delivered")
		return nil
	}), DispatchOptions{MaxAttempts: 3})
	if err != nil {
		t.Fatal(err)
	}
	if res.Delivered != 0 {
		t.Fatalf("duplicate delivered=%d", res.Delivered)
	}

	badSub := Subscription{ID: tenant + "-bad", TenantID: tenant, EventTypes: []string{"run_started"}, Transport: "func", Enabled: true}
	if err := st.UpsertSubscription(ctx, badSub); err != nil {
		t.Fatal(err)
	}
	res, err = st.DispatchOnce(ctx, badSub, funcTransport(func(context.Context, Subscription, Event) error {
		return errors.New("transport down")
	}), DispatchOptions{MaxAttempts: 1})
	if err != nil {
		t.Fatal(err)
	}
	if res.DeadLettered != 1 {
		t.Fatalf("deadLettered=%d", res.DeadLettered)
	}
}
