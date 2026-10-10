package main

import "testing"

func TestPing(t *testing.T) {
	resp := Handle(WireRequest{Schema: WireRequestContract, ID: "go-1", Op: "ping"})
	if !resp.OK || resp.Status != "ok" || resp.Host != "go" {
		t.Fatalf("ping: unexpected response %+v", resp)
	}
	if resp.Schema != WireResponseContract {
		t.Fatalf("ping: wrong schema %q", resp.Schema)
	}
	if resp.Result["version"] != WireVersion {
		t.Fatalf("ping: wrong version %v", resp.Result["version"])
	}
}

func TestValidateRequired(t *testing.T) {
	valid := map[string]any{"schema": "product-forge/product-spec@1", "product_id": "p1", "name": "Demo"}
	resp := Handle(WireRequest{Schema: WireRequestContract, ID: "go-2", Op: "validate",
		ContractName: "product-spec", Payload: valid})
	if !resp.OK || resp.Result["valid"] != true {
		t.Fatalf("validate(valid): expected valid, got %+v", resp)
	}

	missing := map[string]any{"schema": "product-forge/product-spec@1", "name": "Demo"}
	resp = Handle(WireRequest{Schema: WireRequestContract, ID: "go-3", Op: "validate",
		ContractName: "product-spec", Payload: missing})
	if !resp.OK || resp.Result["valid"] != false {
		t.Fatalf("validate(missing product_id): expected invalid, got %+v", resp)
	}
}

func TestValidateWrongSchemaConst(t *testing.T) {
	bad := map[string]any{"schema": "wrong@1", "product_id": "p1", "name": "Demo"}
	valid, errs := Validate("product-spec", bad)
	if valid || len(errs) == 0 {
		t.Fatalf("expected schema-const failure, got valid=%v errs=%v", valid, errs)
	}
}

func TestDescribe(t *testing.T) {
	resp := Handle(WireRequest{Schema: WireRequestContract, ID: "go-4", Op: "describe",
		ContractName: "bom"})
	if !resp.OK {
		t.Fatalf("describe: %+v", resp)
	}
	if resp.Result["schema"] != "product-forge/bom@1" {
		t.Fatalf("describe: wrong schema %v", resp.Result["schema"])
	}
}

func TestUnknownContract(t *testing.T) {
	resp := Handle(WireRequest{Schema: WireRequestContract, ID: "go-5", Op: "validate",
		ContractName: "does-not-exist", Payload: map[string]any{}})
	if resp.OK || resp.Status != "error" {
		t.Fatalf("unknown contract should error: %+v", resp)
	}
}

func TestBadEnvelope(t *testing.T) {
	resp := Handle(WireRequest{Schema: "nope", ID: "go-6", Op: "ping"})
	if resp.OK || resp.Status != "error" {
		t.Fatalf("bad envelope should error: %+v", resp)
	}
}
