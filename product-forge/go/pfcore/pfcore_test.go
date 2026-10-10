package main

import (
	"encoding/json"
	"os"
	"os/exec"
	"runtime"
	"strings"
	"testing"
)

// wireRequest sets the required envelope fields with the canonical schema stamp.
func wireRequest(op string) WireRequest {
	return WireRequest{Schema: WireRequestSchema, ID: "pfcore-1", Op: op}
}

func TestPingIsGoCoreProbe(t *testing.T) {
	resp := Handle(wireRequest("ping"))
	if !resp.OK || resp.Status != "ok" || resp.Host != "go" {
		t.Fatalf("ping: unexpected response %+v", resp)
	}
	if resp.Schema != WireResponseSchema {
		t.Fatalf("ping: wrong response schema %q", resp.Schema)
	}
	if resp.Result["go_version"] == "" || resp.Result["goos"] == "" || resp.Result["goarch"] == "" {
		t.Fatalf("ping: missing runtime probe fields: %+v", resp.Result)
	}
	caps, _ := resp.Result["capabilities"].([]string)
	if len(caps) == 0 {
		t.Fatalf("ping: no capabilities: %+v", resp.Result)
	}
}

func TestRequiredFieldParityWithContractHost(t *testing.T) {
	// Parity with go/contract shapes: same names + same required fields per contract.
	expect := map[string][]string{
		"product-spec":        {"schema", "product_id", "name"},
		"technology-profile":  {"schema", "language"},
		"runtime-profile":     {"schema", "entrypoint", "language"},
		"deployment-profile":  {"schema", "target", "distribution"},
		"license-profile":     {"schema", "license_id", "tier"},
		"entitlement-profile": {"schema", "tier"},
		"component-manifest":  {"schema", "components"},
		"bom":                 {"schema", "project"},
		"evidence":            {"schema", "evidence_id", "kind"},
		"wire-request":        {"schema", "id", "op"},
		"wire-response":       {"schema", "id", "op", "ok", "status", "host"},
	}
	names := ContractNames()
	if len(names) != len(expect) {
		t.Fatalf("contract count drift: have %v", names)
	}
	for name, required := range expect {
		got := RequiredFields(name)
		if len(got) != len(required) {
			t.Fatalf("%s: required-field drift %v != %v", name, got, required)
		}
	}
}

func TestValidateFailClosed(t *testing.T) {
	resp := Handle(WireRequest{Schema: WireRequestSchema, ID: "x", Op: "validate",
		ContractName: "product-spec", Payload: map[string]any{"name": "Demo"}})
	if !resp.OK || resp.Result["valid"] != false {
		t.Fatalf("validate(missing product_id): expected valid=false inside ok envelope, got %+v", resp)
	}
	resp = Handle(WireRequest{Schema: "wrong@1", ID: "x", Op: "ping"})
	if resp.OK {
		t.Fatalf("wrong schema stamp must fail closed, got %+v", resp)
	}
	resp = Handle(WireRequest{Schema: WireRequestSchema, ID: "x", Op: "no-such-op"})
	if resp.OK || !strings.Contains(resp.Error, "unsupported op") {
		t.Fatalf("unknown op must be rejected, got %+v", resp)
	}
}

// TestBuiltBinaryExchangesWithRuntime is the B1 acceptance check: the built pfcore binary
// (PF runtime invocation path) exchanges a valid wire payload with the host.
func TestBuiltBinaryExchangesWithRuntime(t *testing.T) {
	if runtime.GOOS == "js" {
		t.Skip("no process exec")
	}
	goExe := "go"
	bin := "tmp-pfcore-test-host.exe"
	buildCmd := exec.Command(goExe, "build", "-o", bin, ".")
	if out, err := buildCmd.CombinedOutput(); err != nil {
		t.Fatalf("go build: %v\n%s", err, out)
	}
	defer func() { _ = os.Remove(bin) }()

	raw, _ := json.Marshal(WireRequest{Schema: WireRequestSchema, ID: "rt-1", Op: "ping"})
	run := exec.Command("./tmp-pfcore-test-host.exe")
	run.Stdin = strings.NewReader(string(raw))
	out, err := run.Output()
	if err != nil {
		t.Fatalf("pfcore-host ping: %v\n%s", err, out)
	}
	var resp WireResponse
	if err := json.Unmarshal(out, &resp); err != nil {
		t.Fatalf("wire-response decode: %v\n%s", err, out)
	}
	if !resp.OK || resp.Host != "go" || resp.Schema != WireResponseSchema {
		t.Fatalf("runtime exchange: unexpected response %+v", resp)
	}
}
