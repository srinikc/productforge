package tenants

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

const (
	profilesDir = "../../../../config/residency-profiles"
	cellsDir    = "../../../../config/residency-cells"
)

func newTestProvisioner(t *testing.T) *Provisioner {
	t.Helper()
	p, err := NewProvisionerFromConfig(profilesDir, cellsDir)
	if err != nil {
		t.Fatal(err)
	}
	return p
}

func TestProvisionResolvesCompliantCell(t *testing.T) {
	p := newTestProvisioner(t)
	res, err := p.Provision(ProvisionRequest{TenantID: "t1", Region: "IN", RequiredCapabilities: []string{"pii", "in-country"}})
	if err != nil {
		t.Fatalf("provision: %v", err)
	}
	if res.CellID != "in-1" || res.Region != "IN" {
		t.Fatalf("unexpected cell: %+v", res)
	}
}

func TestProvisionFailsClosed(t *testing.T) {
	p := newTestProvisioner(t)
	// unknown region (no versioned policy) -> fail closed
	if _, err := p.Provision(ProvisionRequest{TenantID: "t", Region: "ZZ"}); err == nil {
		t.Fatal("unknown region must fail closed")
	}
	// no attested cell satisfies the capability -> fail closed
	if _, err := p.Provision(ProvisionRequest{TenantID: "t", Region: "US", RequiredCapabilities: []string{"gpu"}}); err == nil {
		t.Fatal("unsatisfiable capability must fail closed")
	}
	// missing fields -> fail closed
	if _, err := p.Provision(ProvisionRequest{Region: "US"}); err == nil {
		t.Fatal("missing tenant_id must fail closed")
	}
	if _, err := p.Provision(ProvisionRequest{TenantID: "t"}); err == nil {
		t.Fatal("missing region must fail closed")
	}
}

func TestProvisionHandler(t *testing.T) {
	p := newTestProvisioner(t)
	h := p.Handler()

	post := func(body string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(http.MethodPost, "/residency/provision", bytes.NewBufferString(body))
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		return w
	}

	w := post(`{"tenant_id":"t1","region":"US","required_capabilities":["pii"]}`)
	if w.Code != http.StatusOK {
		t.Fatalf("want 200, got %d (%s)", w.Code, w.Body.String())
	}
	var got ProvisionResult
	if err := json.Unmarshal(w.Body.Bytes(), &got); err != nil || got.CellID != "us-1" {
		t.Fatalf("bad body: %s err=%v", w.Body.String(), err)
	}
	if post(`{"tenant_id":"t","region":"ZZ"}`).Code != http.StatusUnprocessableEntity {
		t.Fatal("unknown region should be 422")
	}
	if post(`{"tenant_id":"t","region":"US","required_capabilities":["gpu"]}`).Code != http.StatusServiceUnavailable {
		t.Fatal("no compliant cell should be 503")
	}
	if post(`not json`).Code != http.StatusBadRequest {
		t.Fatal("bad body should be 400")
	}
}
