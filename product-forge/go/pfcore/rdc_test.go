// rdc_test.go — Tests for Runtime Dependency Compiler (A5, BI-PF-0399)
package main

import (
	"strings"
	"testing"
)

func TestRDCTargetValidation(t *testing.T) {
	validTargets := [][]string{
		{"linux", "amd64"},
		{"linux", "arm64"},
		{"windows", "amd64"},
		{"darwin", "arm64"},
		{"darwin", "amd64"},
	}
	for _, tgt := range validTargets {
		if !ValidateTarget(tgt[0], tgt[1]) {
			t.Errorf("ValidateTarget(%s, %s) expected true, got false", tgt[0], tgt[1])
		}
	}

	invalidTargets := [][]string{
		{"solaris", "sparc"},
		{"windows", "arm"},
		{"linux", "mips"},
	}
	for _, tgt := range invalidTargets {
		if ValidateTarget(tgt[0], tgt[1]) {
			t.Errorf("ValidateTarget(%s, %s) expected false, got true", tgt[0], tgt[1])
		}
	}
}

func TestRDCIPLeakageGuard(t *testing.T) {
	// Customer edition with raw .py must fail closed
	reqBad := WireRequest{
		Schema: WireRequestSchema,
		ID:     "test-ip-bad",
		Op:     "rdc.validate_ip",
		Payload: map[string]any{
			"edition": "enterprise",
			"files": []any{
				"bin/pf-core",
				"core/licensing.py", // Unprotected raw .py!
			},
		},
	}
	respBad := ValidateIPLeakage(reqBad)
	if respBad.OK {
		t.Fatal("ValidateIPLeakage expected OK=false for raw .py in enterprise edition")
	}
	if !strings.Contains(respBad.Error, "IP_LEAKAGE_DETECTED") {
		t.Errorf("Expected error containing IP_LEAKAGE_DETECTED, got %q", respBad.Error)
	}

	// Customer edition with compiled binaries only must pass
	reqGood := WireRequest{
		Schema: WireRequestSchema,
		ID:     "test-ip-good",
		Op:     "rdc.validate_ip",
		Payload: map[string]any{
			"edition": "enterprise",
			"files": []any{
				"bin/pf-core",
				"lib/core_runtime.so",
				"lib/api_runtime.so",
			},
		},
	}
	respGood := ValidateIPLeakage(reqGood)
	if !respGood.OK {
		t.Fatalf("ValidateIPLeakage expected OK=true for compiled files, got error: %s", respGood.Error)
	}

	// Community edition with raw .py is allowed
	reqCommunity := WireRequest{
		Schema: WireRequestSchema,
		ID:     "test-ip-community",
		Op:     "rdc.validate_ip",
		Payload: map[string]any{
			"edition": "community",
			"files": []any{
				"core/licensing.py",
			},
		},
	}
	respCommunity := ValidateIPLeakage(reqCommunity)
	if !respCommunity.OK {
		t.Fatalf("ValidateIPLeakage expected OK=true for community edition, got error: %s", respCommunity.Error)
	}
}

func TestRDCCompose(t *testing.T) {
	// Compose for Linux amd64
	reqLinux := WireRequest{
		Schema: WireRequestSchema,
		ID:     "test-compose-linux",
		Op:     "rdc.compose",
		Payload: map[string]any{
			"edition":     "enterprise",
			"target_os":   "linux",
			"target_arch": "amd64",
			"dry_run":     true,
		},
	}
	respLinux := Compose(reqLinux)
	if !respLinux.OK {
		t.Fatalf("Compose for linux/amd64 failed: %s", respLinux.Error)
	}
	res := respLinux.Result
	if res["target_platform"] != "linux/amd64" {
		t.Errorf("expected target_platform linux/amd64, got %v", res["target_platform"])
	}
	bins := res["native_binaries"].([]string)
	if len(bins) == 0 || bins[0] != "pf-core" {
		t.Errorf("expected native binary pf-core, got %v", bins)
	}

	// Compose for Windows amd64
	reqWin := WireRequest{
		Schema: WireRequestSchema,
		ID:     "test-compose-win",
		Op:     "rdc.compose",
		Payload: map[string]any{
			"edition":     "enterprise",
			"target_os":   "windows",
			"target_arch": "amd64",
			"dry_run":     true,
		},
	}
	respWin := Compose(reqWin)
	if !respWin.OK {
		t.Fatalf("Compose for windows/amd64 failed: %s", respWin.Error)
	}
	winBins := respWin.Result["native_binaries"].([]string)
	if len(winBins) == 0 || winBins[0] != "pf-core.exe" {
		t.Errorf("expected native binary pf-core.exe for windows, got %v", winBins)
	}

	// Compose with unsupported target
	reqBad := WireRequest{
		Schema: WireRequestSchema,
		ID:     "test-compose-bad",
		Op:     "rdc.compose",
		Payload: map[string]any{
			"edition":     "enterprise",
			"target_os":   "freebsd",
			"target_arch": "riscv64",
		},
	}
	respBad := Compose(reqBad)
	if respBad.OK {
		t.Fatal("expected Compose with unsupported target to fail")
	}
}

func TestRDCPlan(t *testing.T) {
	reqPlan := WireRequest{
		Schema: WireRequestSchema,
		ID:     "test-plan",
		Op:     "rdc.plan",
		Payload: map[string]any{
			"edition":     "enterprise",
			"target_os":   "linux",
			"target_arch": "amd64",
		},
	}
	respPlan := Plan(reqPlan)
	if !respPlan.OK {
		t.Fatalf("Plan failed: %s", respPlan.Error)
	}
	if respPlan.Result["total_files"].(int) == 0 {
		t.Error("expected non-zero total_files in plan")
	}
}
