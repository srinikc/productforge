package main

import "testing"

func TestEventEnvelopeRejectsUnknownTopLevelFields(t *testing.T) {
	payload := map[string]any{
		"schema": "product-forge/event-envelope@1", "event_id": "e1",
		"event_type": "run_started", "event_version": "1",
		"occurred_at": "2026-01-01T00:00:00", "seq": 1,
		"unexpected": "x",
	}
	ok, errs := Validate("event-envelope", payload)
	if ok || len(errs) == 0 {
		t.Fatalf("unknown top-level field accepted: ok=%v errs=%v", ok, errs)
	}
}

func TestEventEnvelopeRequiresSeq(t *testing.T) {
	payload := map[string]any{
		"schema": "product-forge/event-envelope@1", "event_id": "e1",
		"event_type": "run_started", "event_version": "1",
		"occurred_at": "2026-01-01T00:00:00",
	}
	ok, _ := Validate("event-envelope", payload)
	if ok {
		t.Fatal("missing seq accepted")
	}
}

func TestEventEnvelopeExtensionsAllowed(t *testing.T) {
	payload := map[string]any{
		"schema": "product-forge/event-envelope@1", "event_id": "e1",
		"event_type": "run_started", "event_version": "1",
		"occurred_at": "2026-01-01T00:00:00", "seq": 1,
		"extensions": map[string]any{"vendor": "x"},
	}
	ok, errs := Validate("event-envelope", payload)
	if !ok {
		t.Fatalf("extensions rejected: %v", errs)
	}
}

func TestWebhookSignatureVerification(t *testing.T) {
	body := []byte(`{"event_id":"e1"}`)
	sig := WebhookSignature(body, "secret")
	if !VerifyWebhookSignature(body, sig, "secret") {
		t.Fatal("valid signature rejected")
	}
	if VerifyWebhookSignature(body, sig, "wrong") {
		t.Fatal("invalid secret accepted")
	}
	if VerifyWebhookSignature(body, "", "secret") {
		t.Fatal("empty signature accepted")
	}
}

func TestEventingContractsRejectUnknownFields(t *testing.T) {
	cases := map[string]map[string]any{
		"subscription":     {"schema": "product-forge/subscription@1", "id": "s1", "transport": "webhook", "unexpected": "x"},
		"alert-rule":       {"schema": "product-forge/alert-rule@1", "event_type": "run_failed", "channels": []any{"email"}, "unexpected": "x"},
		"webhook-delivery": {"schema": "product-forge/webhook-delivery@1", "delivery_id": "d1", "event_id": "e1", "subscription_id": "s1", "target_url": "https://example.test/hook", "unexpected": "x"},
	}
	for name, payload := range cases {
		if ok, _ := Validate(name, payload); ok {
			t.Fatalf("%s accepted unknown top-level field", name)
		}
	}
}

func TestWebhookHeadersAndMetricsParity(t *testing.T) {
	body := []byte(`{"event_id":"e1"}`)
	h := WebhookHeaders("e1", body, "secret")
	if h[WebhookIdempotencyHeader] != "e1" {
		t.Fatal("idempotency header must equal event_id")
	}
	if !VerifyWebhookSignature(body, h[WebhookSignatureHeader], "secret") {
		t.Fatal("canonical header signature rejected")
	}
	if ContractMetrics["validation_failures"] != "contract_validation_failures_total" {
		t.Fatal("metric parity drift")
	}
}
