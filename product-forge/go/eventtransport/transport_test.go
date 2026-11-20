package eventtransport

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"productforge/edpdata"
)

func TestInprocCallback(t *testing.T) {
	i := NewInproc()
	called := 0
	i.On("run_started", func(context.Context, edpdata.Event) error { called++; return nil })
	if err := i.Deliver(context.Background(), edpdata.Subscription{}, edpdata.Event{Type: "run_started"}); err != nil {
		t.Fatal(err)
	}
	if called != 1 {
		t.Fatalf("called=%d", called)
	}
}

func TestWebhookHMACAndIdempotency(t *testing.T) {
	var gotSig, gotIdem string
	srv := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotSig = r.Header.Get("X-PF-Signature")
		gotIdem = r.Header.Get("X-PF-Idempotency-Key")
		body := make([]byte, r.ContentLength)
		r.Body.Read(body)
		mac := hmac.New(sha256.New, []byte("secret"))
		mac.Write([]byte(r.Header.Get("X-PF-Timestamp") + "." + string(body)))
		if gotSig != "sha256="+hex.EncodeToString(mac.Sum(nil)) {
			t.Errorf("bad signature")
		}
		w.WriteHeader(200)
	}))
	defer srv.Close()
	w := NewWebhook()
	w.Client = srv.Client()
	w.AllowPrivate = true
	if err := w.Deliver(context.Background(), edpdata.Subscription{Target: srv.URL, AuthRef: "secret"}, edpdata.Event{EventID: "e1", Type: "x", Payload: []byte(`{"a":1}`)}); err != nil {
		t.Fatal(err)
	}
	if gotIdem != "e1" {
		t.Fatalf("idem=%s", gotIdem)
	}
	if !strings.HasPrefix(gotSig, "sha256=") {
		t.Fatalf("sig=%s", gotSig)
	}
}

func TestWebhookPermanentAndDuplicate(t *testing.T) {
	for _, code := range []int{400, 409} {
		srv := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(code) }))
		w := NewWebhook()
		w.Client = srv.Client()
		w.AllowPrivate = true
		err := w.Deliver(context.Background(), edpdata.Subscription{Target: srv.URL, AuthRef: "secret"}, edpdata.Event{EventID: "e1", Type: "x"})
		if code == 409 && err != nil {
			t.Fatalf("409 should succeed: %v", err)
		}
		if code == 400 && !edpdata.IsPermanent(err) {
			t.Fatalf("400 should be permanent: %v", err)
		}
		srv.Close()
	}
}

func TestNotifyInAppAndPriority(t *testing.T) {
	var body map[string]any
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewDecoder(r.Body).Decode(&body)
		w.WriteHeader(200)
	}))
	defer srv.Close()
	n := NewNotify()
	n.APIURL = srv.URL
	n.MinPriority = "medium"
	if err := n.Deliver(context.Background(), edpdata.Subscription{TenantID: "p"}, edpdata.Event{EventID: "e1", Type: "run_started", Payload: []byte(`{}`)}); err != nil {
		t.Fatal(err)
	}
	if body["priority"] != "medium" {
		t.Fatalf("priority=%v", body["priority"])
	}
}

func TestRegistryTenantLookup(t *testing.T) {
	r := NewRegistry()
	in := NewInproc()
	r.Register("inproc", in)
	if _, ok := r.Get("inproc"); !ok {
		t.Fatal("missing transport")
	}
}
