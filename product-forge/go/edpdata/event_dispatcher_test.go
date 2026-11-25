package edpdata

import (
	"context"
	"testing"
	"time"
)

func TestSubscriptionMatching(t *testing.T) {
	sub := Subscription{EventTypes: []string{"run_started", "run_finished"}}
	if !matchesSubscription(sub, Event{Type: "run_started"}) {
		t.Fatal("expected type match")
	}
	if matchesSubscription(sub, Event{Type: "other"}) {
		t.Fatal("unexpected type match")
	}
	if !matchesSubscription(Subscription{}, Event{Type: "anything"}) {
		t.Fatal("empty type list must match all")
	}
}

func TestBackoffDoublesAndCaps(t *testing.T) {
	if got := backoff(time.Second, 1); got != time.Second {
		t.Fatalf("attempt1=%s", got)
	}
	if got := backoff(time.Second, 3); got != 4*time.Second {
		t.Fatalf("attempt3=%s", got)
	}
	if got := backoff(time.Hour, 10); got != time.Hour {
		t.Fatalf("cap=%s", got)
	}
}

func TestSubscriptionValidation(t *testing.T) {
	st := NewEventStore(&fakeStore{})
	if err := st.UpsertSubscription(context.Background(), Subscription{}); err == nil {
		t.Fatal("expected validation error")
	}
}

func TestDispatchOptionsDefaults(t *testing.T) {
	o := DispatchOptions{}.normalize()
	if o.Limit != 100 || o.MaxAttempts != 5 || o.BaseBackoff != time.Second || o.Now == nil {
		t.Fatalf("defaults=%+v", o)
	}
}

func TestFilterMatchesPayload(t *testing.T) {
	sub := Subscription{Filter: map[string]string{"kind": "run"}}
	if !matchesFilter(sub, Event{Payload: []byte(`{"kind":"run"}`)}) {
		t.Fatal("expected filter match")
	}
	if matchesFilter(sub, Event{Payload: []byte(`{"kind":"other"}`)}) {
		t.Fatal("unexpected filter match")
	}
	if matchesFilter(sub, Event{Payload: []byte(`not-json`)}) {
		t.Fatal("invalid payload matched filter")
	}
}
