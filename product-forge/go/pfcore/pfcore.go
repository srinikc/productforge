// pfcore.go is the PF native Go core library (B1, BI-PF-0394): the new destination for
// shipped/sensitive logic ("Go-first for new work", LOCKED baseline BI-PF-0387 / ADR BI-PF-0388).
// It speaks the SAME A1 wire contract as the contract host (core/contracts.py <-> go/contract)
// so the PF runtime can invoke it through one seam. Stdlib only so `go build` always succeeds;
// it never translates existing Python. Layout mirrors go/contract: single package main dir.
package main

import (
	"fmt"
	"runtime"
	"sort"
)

// WireVersion mirrors the A1 wire contract version (core/contracts.py WIRE_VERSION).
const WireVersion = "1"

// Envelope schema constants (must match core/contracts.py record() stamping + go/contract).
const (
	WireRequestSchema  = "product-forge/wire-request@1"
	WireResponseSchema = "product-forge/wire-response@1"
)

// WireRequest is the Go<->Python request envelope (same field shape as go/contract:
// required-field parity is asserted by tests, not assumed).
type WireRequest struct {
	Schema       string         `json:"schema"`
	ID           string         `json:"id"`
	Op           string         `json:"op"`
	ContractName string         `json:"contract_name"`
	Payload      map[string]any `json:"payload"`
	Source       string         `json:"source"`
}

// WireResponse is the Go<->Python response envelope.
type WireResponse struct {
	Schema       string         `json:"schema"`
	ID           string         `json:"id"`
	Op           string         `json:"op"`
	OK           bool           `json:"ok"`
	Status       string         `json:"status"`
	Host         string         `json:"host"`
	ContractName string         `json:"contract_name"`
	Result       map[string]any `json:"result"`
	Error        string         `json:"error"`
}

// contractShape mirrors the canonical contract required fields + schema constant.
type contractShape struct {
	schemaConst string
	required    []string
}

// contractShapes mirrors core/contracts.py CONTRACTS and go/contract (parity asserted by tests).
var contractShapes = map[string]contractShape{
	"product-spec":        {"product-forge/product-spec@1", []string{"schema", "product_id", "name"}},
	"technology-profile":  {"product-forge/technology-profile@1", []string{"schema", "language"}},
	"runtime-profile":     {"product-forge/runtime-profile@1", []string{"schema", "entrypoint", "language"}},
	"deployment-profile":  {"product-forge/deployment-profile@1", []string{"schema", "target", "distribution"}},
	"license-profile":     {"product-forge/license-profile@1", []string{"schema", "license_id", "tier"}},
	"entitlement-profile": {"product-forge/entitlement-profile@1", []string{"schema", "tier"}},
	"component-manifest":  {"product-forge/component-manifest@1", []string{"schema", "components"}},
	"bom":                 {"product-forge/bom@1", []string{"schema", "project"}},
	"evidence":            {"product-forge/evidence@1", []string{"schema", "evidence_id", "kind"}},
	"wire-request":        {"product-forge/wire-request@1", []string{"schema", "id", "op"}},
	"wire-response":       {"product-forge/wire-response@1", []string{"schema", "id", "op", "ok", "status", "host"}},
}

// ContractNames returns the known contract names (sorted, deterministic describe output).
func ContractNames() []string {
	names := make([]string, 0, len(contractShapes))
	for n := range contractShapes {
		names = append(names, n)
	}
	sort.Strings(names)
	return names
}

// RequiredFields returns the required field names for a contract (nil if unknown).
func RequiredFields(name string) []string {
	if s, ok := contractShapes[name]; ok {
		out := make([]string, len(s.required))
		copy(out, s.required)
		return out
	}
	return nil
}

// Validate checks a payload against the mirrored contract shape (fail-closed).
func Validate(name string, payload map[string]any) (bool, []string) {
	shape, ok := contractShapes[name]
	if !ok {
		return false, []string{"unknown contract: " + name}
	}
	if payload == nil {
		return false, []string{"payload must be an object"}
	}
	errs := []string{}
	for _, f := range shape.required {
		v, present := payload[f]
		if !present {
			errs = append(errs, f+": required")
			continue
		}
		if s, isStr := v.(string); isStr && s == "" {
			errs = append(errs, f+": required")
		}
	}
	if got, present := payload["schema"]; present {
		if s, isStr := got.(string); isStr && s != shape.schemaConst {
			errs = append(errs, fmt.Sprintf("schema: must equal %s", shape.schemaConst))
		}
	}
	return len(errs) == 0, errs
}

// Capabilities are the Go-native features pfcore exposes (grows as new shipped/sensitive
// features land here per the language rule).
func Capabilities() []string {
	return []string{"ping", "describe", "validate"}
}

// HostID is the distinct pfcore host tag (the wire contract's `host` enum is {python, go}).
const HostID = "go-pfcore"

// Ping answers the standard seam ping - Go-native identity + environment probe (B1 accept:
// a new Go feature invokable from the PF runtime). The contract `host` field stays the enum
// value "go"; pfcore's distinct identity rides in result.host_id (guideline 11: no widening).
func Ping(req WireRequest) WireResponse {
	return response(req, true, "ok", map[string]any{
		"version":      WireVersion,
		"host":         "go",
		"host_id":      HostID,
		"go_version":   runtime.Version(),
		"goos":         runtime.GOOS,
		"goarch":       runtime.GOARCH,
		"capabilities": Capabilities(),
	}, "")
}

// SupportedOps lists the seam ops pfcore understands.
func SupportedOps() []string { return []string{"ping", "describe", "validate"} }

func response(req WireRequest, ok bool, status string, result map[string]any, errMsg string) WireResponse {
	if result == nil {
		result = map[string]any{}
	}
	return WireResponse{Schema: WireResponseSchema, ID: req.ID, Op: req.Op, OK: ok, Status: status,
		Host: "go", ContractName: req.ContractName, Result: result, Error: errMsg}
}

// Handle routes a wire request (standard seam parity with go/contract; pfcore-tagged).
func Handle(req WireRequest) WireResponse {
	if req.Schema != WireRequestSchema {
		return response(req, false, "error", nil,
			fmt.Sprintf("invalid wire-request: schema must be %s", WireRequestSchema))
	}
	if req.ID == "" || req.Op == "" {
		return response(req, false, "error", nil, "invalid wire-request: id and op are required")
	}
	switch req.Op {
	case "ping":
		return Ping(req)
	case "describe":
		shape, ok := contractShapes[req.ContractName]
		if !ok {
			return response(req, false, "error", nil, "unknown contract: "+req.ContractName)
		}
		return response(req, true, "ok", map[string]any{
			"contract": req.ContractName, "required": shape.required,
			"schema": shape.schemaConst,
		}, "")
	case "validate":
		if _, ok := contractShapes[req.ContractName]; !ok {
			return response(req, false, "error", nil, "unknown contract: "+req.ContractName)
		}
		valid, errs := Validate(req.ContractName, req.Payload)
		return response(req, true, "ok", map[string]any{
			"contract": req.ContractName, "valid": valid, "errors": errs,
		}, "")
	default:
		return response(req, false, "error", nil, "unsupported op: "+req.Op)
	}
}
