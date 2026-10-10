// Package main is the Go side of the Product Forge Go<->Python wire contract (BI-PF-0393).
//
// It is the minimal "Go host" reference for A1: it consumes the canonical wire-request
// envelope emitted by the Python core (core/contracts.py), validates the payload against the
// mirrored contract shape, and emits a canonical wire-response the Python core can consume.
//
// The Python side is the schema source of truth; the required-field tables below mirror it and
// are cross-checked by the Python e2e test (test-framework/tests/pipeline/test_contracts.py).
package main

import (
	"fmt"
	"sort"
)

const (
	// WireRequestContract / WireResponseContract are the envelope schema constants.
	WireRequestContract  = "product-forge/wire-request@1"
	WireResponseContract = "product-forge/wire-response@1"
	// WireVersion is the wire protocol version.
	WireVersion = "1"
)

// WireRequest is the Go<->Python request envelope (the "schema" key discriminates the contract).
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

// contractShapes mirrors core/contracts.py CONTRACTS (cross-checked by the Python e2e test).
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

// ContractNames returns the known contract names (sorted for deterministic describe output).
func ContractNames() []string {
	names := make([]string, 0, len(contractShapes))
	for n := range contractShapes {
		names = append(names, n)
	}
	sort.Strings(names)
	return names
}

// RequiredFields returns the required field names for a contract.
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

func response(req WireRequest, ok bool, status string, result map[string]any, errMsg string) WireResponse {
	if result == nil {
		result = map[string]any{}
	}
	return WireResponse{
		Schema:       WireResponseContract,
		ID:           req.ID,
		Op:           req.Op,
		OK:           ok,
		Status:       status,
		Host:         "go",
		ContractName: req.ContractName,
		Result:       result,
		Error:        errMsg,
	}
}

// Handle processes a wire request and returns a canonical wire response (never panics).
func Handle(req WireRequest) WireResponse {
	if req.Schema != WireRequestContract {
		return response(req, false, "error", nil,
			fmt.Sprintf("invalid wire-request: schema must be %s", WireRequestContract))
	}
	if req.ID == "" || req.Op == "" {
		return response(req, false, "error", nil, "invalid wire-request: id and op are required")
	}
	switch req.Op {
	case "ping":
		return response(req, true, "ok", map[string]any{
			"version": WireVersion, "host": "go", "contracts": ContractNames(),
		}, "")
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
