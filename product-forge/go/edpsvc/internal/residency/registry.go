// Package residency is the EDP-05 versioned, fail-closed residency & transfer policy registry.
//
// It loads counsel-owned policy profiles from config/residency-profiles/*.json (IN-v1, US-v1, ...), indexes
// them by region + version, and resolves the effective policy for a region. Resolution is FAIL-CLOSED: an
// unknown or missing region returns ErrUnknownRegion - never a default - so a tenant can never be provisioned
// against an unstated residency policy.
//
// POLICY EVALUATION IS NOT done here: this package only owns the registry + profiles. A transfer/residency
// decision is delegated to an Evaluator (implemented by EDP-11 / BI-PF-1303: ResidencyPolicy + RegionResolver),
// so the registry is the single source of truth for the *policies* while EDP-11 owns the *evaluation*.
package residency

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

// ErrUnknownRegion is returned by Resolve for any region with no registered policy (fail-closed).
var ErrUnknownRegion = errors.New("residency: no policy registered for region")

// Policy is one residency & transfer policy profile (one JSON file). The CONTENT is owned by counsel; the
// registry only validates its shape and version, never invents defaults.
type Policy struct {
	ID                  string   `json:"id"`                    // e.g. "in-v1"
	Version             string   `json:"version"`               // e.g. "1.0"
	Region              string   `json:"region"`                // ISO region code, e.g. "IN", "US"
	DisplayName         string   `json:"display_name"`          // e.g. "India (IN-v1)"
	Residency           string   `json:"residency"`             // e.g. "in-region" | "in-country"
	CrossBorderTransfer string   `json:"cross_border_transfer"` // e.g. "restricted" | "allowed" | "conditioned"
	AllowedRegions      []string `json:"allowed_regions"`       // regions data may reside in / transfer to
	RetentionDays       int      `json:"retention_days"`        // >= 0; 0 = unspecified (counsel decides)
	EncryptionAtRest    bool     `json:"encryption_at_rest"`
	EncryptionInTransit bool     `json:"encryption_in_transit"`
	Notes               string   `json:"notes"`
}

// validate fails closed on any missing/blank required field or bad version.
func (p Policy) validate() error {
	for field, v := range map[string]string{
		"id": p.ID, "version": p.Version, "region": p.Region,
		"residency": p.Residency, "cross_border_transfer": p.CrossBorderTransfer,
	} {
		if strings.TrimSpace(v) == "" {
			return fmt.Errorf("residency: policy %q: required field %q is empty", p.ID, field)
		}
	}
	if len(p.AllowedRegions) == 0 {
		return fmt.Errorf("residency: policy %q: allowed_regions is empty", p.ID)
	}
	if _, ok := parseVersion(p.Version); !ok {
		return fmt.Errorf("residency: policy %q: version %q is not <major>[.<minor>]", p.ID, p.Version)
	}
	if p.RetentionDays < 0 {
		return fmt.Errorf("residency: policy %q: retention_days must be >= 0", p.ID)
	}
	return nil
}

// Registry is an immutable, versioned set of policies indexed by region.
type Registry struct {
	dir      string
	byRegion map[string]map[string]Policy // region -> version -> policy
}

// LoadDir loads and validates every *.json profile in dir, returning a Registry (fail-closed on any
// invalid/duplicate profile). A directory with no profiles is an error - an empty registry cannot be trusted.
func LoadDir(dir string) (*Registry, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, fmt.Errorf("residency: read profiles dir %q: %w", dir, err)
	}
	r := &Registry{dir: dir, byRegion: map[string]map[string]Policy{}}
	seen := map[string]string{} // id -> file (duplicate id guard)
	n := 0
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".json") {
			continue
		}
		raw, err := os.ReadFile(filepath.Join(dir, e.Name()))
		if err != nil {
			return nil, fmt.Errorf("residency: read %s: %w", e.Name(), err)
		}
		var p Policy
		if err := json.Unmarshal(raw, &p); err != nil {
			return nil, fmt.Errorf("residency: %s is not a policy profile: invalid JSON: %w", e.Name(), err)
		}
		if err := p.validate(); err != nil {
			return nil, fmt.Errorf("residency: %s is not a policy profile: %w "+
				"(this directory must contain ONLY policy profiles; keep region-cell/keyring JSON in a separate directory)", e.Name(), err)
		}
		if prev, dup := seen[p.ID]; dup {
			return nil, fmt.Errorf("residency: duplicate policy id %q (%s and %s)", p.ID, prev, e.Name())
		}
		seen[p.ID] = e.Name()
		if r.byRegion[p.Region] == nil {
			r.byRegion[p.Region] = map[string]Policy{}
		}
		if _, dup := r.byRegion[p.Region][p.Version]; dup {
			return nil, fmt.Errorf("residency: duplicate policy for region %s version %s", p.Region, p.Version)
		}
		r.byRegion[p.Region][p.Version] = p
		n++
	}
	if n == 0 {
		return nil, fmt.Errorf("residency: no policy profiles found in %q", dir)
	}
	return r, nil
}

// Resolve returns the LATEST policy for region (fail-closed: ErrUnknownRegion when none is registered).
func (r *Registry) Resolve(region string) (Policy, error) {
	vers, ok := r.byRegion[strings.ToUpper(strings.TrimSpace(region))]
	if !ok || len(vers) == 0 {
		return Policy{}, fmt.Errorf("%w: %q", ErrUnknownRegion, region)
	}
	return vers[r.latestVersion(region)], nil
}

// Regions lists the regions with at least one registered policy (sorted).
func (r *Registry) Regions() []string {
	out := make([]string, 0, len(r.byRegion))
	for reg := range r.byRegion {
		out = append(out, reg)
	}
	sort.Strings(out)
	return out
}

// Versions lists the versions registered for a region (sorted ascending).
func (r *Registry) Versions(region string) []string {
	vers := r.byRegion[strings.ToUpper(strings.TrimSpace(region))]
	out := make([]string, 0, len(vers))
	for v := range vers {
		out = append(out, v)
	}
	sort.Slice(out, func(i, j int) bool { return lessVersion(out[i], out[j]) })
	return out
}

func (r *Registry) latestVersion(region string) string {
	out := ""
	for v := range r.byRegion[region] {
		if out == "" || lessVersion(out, v) {
			out = v
		}
	}
	return out
}

func parseVersion(v string) ([]int, bool) {
	parts := strings.Split(strings.TrimSpace(v), ".")
	if len(parts) == 0 || len(parts) > 3 {
		return nil, false
	}
	out := make([]int, 0, len(parts))
	for _, p := range parts {
		n, err := strconv.Atoi(p)
		if err != nil || n < 0 {
			return nil, false
		}
		out = append(out, n)
	}
	return out, true
}

func lessVersion(a, b string) bool {
	av, aok := parseVersion(a)
	bv, bok := parseVersion(b)
	if !aok || !bok {
		return a < b
	}
	for i := 0; i < len(av) || i < len(bv); i++ {
		var ai, bi int
		if i < len(av) {
			ai = av[i]
		}
		if i < len(bv) {
			bi = bv[i]
		}
		if ai != bi {
			return ai < bi
		}
	}
	return false
}

// TransferRequest is the input to a residency evaluation (a cross-border transfer decision).
type TransferRequest struct {
	TenantID  string
	Region    string   // the region the data currently resides in
	Target    string   // the destination region of the transfer
	DataClass []string // e.g. ["pii", "health"]
}

// Decision is the outcome of a residency evaluation.
type Decision struct {
	Allowed   bool
	PolicyID  string
	PolicyVer string
	Reasons   []string
}

// Evaluator is the seam the registry delegates POLICY EVALUATION to. The registry owns the policies; a
// concrete Evaluator (EDP-11 / BI-PF-1303: ResidencyPolicy + RegionResolver) owns the decision. Passing the
// resolved Policy (not the raw registry) keeps the evaluator stateless and the registry the single source.
type Evaluator interface {
	Evaluate(req TransferRequest, policy Policy) (Decision, error)
}
