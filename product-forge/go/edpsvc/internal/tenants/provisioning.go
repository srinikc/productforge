// Package tenants owns the EDP-11 fail-closed tenant provisioning decision: a tenant may only be provisioned
// into a region cell that (a) has a versioned residency policy, and (b) is an ATTESTED cell satisfying the
// tenant's required capabilities. Any missing link -> an error; there is no implicit/default cell.
//
// It exposes two things: a pure Provisioner.Provision(...) (library) and Provisioner.Handler() (an http.Handler
// for the API surface). Persisting the tenant->cell assignment and mounting the route into the enterprise
// tenant lifecycle live in the enterprise/lifecycle layer (schema >=0020) - this package stays decision-only.
package tenants

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"path/filepath"
	"strings"

	"productforge/edpsvc/internal/residency"
)

// ProvisionRequest is the input to a provisioning decision.
type ProvisionRequest struct {
	TenantID             string   `json:"tenant_id"`
	Region               string   `json:"region"`
	RequiredCapabilities []string `json:"required_capabilities"`
}

// ProvisionResult is the resolved placement (the cell the tenant is compliant with).
type ProvisionResult struct {
	TenantID     string   `json:"tenant_id"`
	CellID       string   `json:"cell_id"`
	Region       string   `json:"region"`
	Capabilities []string `json:"capabilities"`
}

// Provisioner decides a tenant's region cell, fail-closed.
type Provisioner struct {
	registry *residency.Registry
	resolver *residency.RegionResolver
}

// NewProvisioner builds a Provisioner from a policy registry + region resolver.
func NewProvisioner(registry *residency.Registry, resolver *residency.RegionResolver) *Provisioner {
	return &Provisioner{registry: registry, resolver: resolver}
}

// NewProvisionerFromConfig builds a Provisioner from the residency config: policiesDir (config/residency-profiles,
// policy profiles ONLY) and cellsDir (config/residency-cells: region-cells.json + attestation-keys.json). The
// two are separate directories so the policy loader never sees a non-policy JSON.
func NewProvisionerFromConfig(policiesDir, cellsDir string) (*Provisioner, error) {
	registry, err := residency.LoadDir(policiesDir)
	if err != nil {
		return nil, err
	}
	provider := residency.ConfigProvider{
		CellsPath:   filepath.Join(cellsDir, "region-cells.json"),
		KeyringPath: filepath.Join(cellsDir, "attestation-keys.json"),
	}
	return NewProvisioner(registry, residency.NewRegionResolver(provider)), nil
}

// Provision returns the compliant cell for a tenant, or an error (fail-closed): unknown/empty region, no
// versioned policy, or no attested capability-satisfying cell. Nothing is defaulted.
func (p *Provisioner) Provision(req ProvisionRequest) (ProvisionResult, error) {
	if strings.TrimSpace(req.TenantID) == "" || strings.TrimSpace(req.Region) == "" {
		return ProvisionResult{}, errors.New("tenants: tenant_id and region are required")
	}
	policy, err := p.registry.Resolve(req.Region)
	if err != nil {
		return ProvisionResult{}, fmt.Errorf("tenants: residency policy: %w", err)
	}
	cell, err := p.resolver.Resolve(policy.Region, req.RequiredCapabilities)
	if err != nil {
		return ProvisionResult{}, fmt.Errorf("tenants: region cell: %w", err)
	}
	return ProvisionResult{
		TenantID: req.TenantID, CellID: cell.ID, Region: cell.Region, Capabilities: cell.Capabilities,
	}, nil
}

// Handler is the mountable HTTP surface for provisioning (POST JSON ProvisionRequest -> 200 ProvisionResult).
// Fail-closed status mapping: missing fields -> 400; no/unknown residency policy -> 422; no compliant cell ->
// 503. The enterprise lifecycle mounts this (see the residency-routes block); this package does not.
func (p *Provisioner) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/residency/provision", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		var req ProvisionRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "invalid JSON body", http.StatusBadRequest)
			return
		}
		res, err := p.Provision(req)
		if err != nil {
			code := http.StatusUnprocessableEntity
			if errors.Is(err, residency.ErrNoCompliantCell) {
				code = http.StatusServiceUnavailable
			}
			http.Error(w, err.Error(), code)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(res)
	})
	return mux
}
