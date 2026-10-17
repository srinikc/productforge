package residency

import (
	"errors"
	"fmt"
	"sort"
	"strings"
	"time"
)

// ErrNoCompliantCell is returned when no attested, capability-satisfying cell exists for a region (fail-closed).
var ErrNoCompliantCell = errors.New("residency: no compliant region cell")

// CellProvider supplies the region cells + trusted keyring. Config-backed today (LoadCells/LoadKeyring);
// a DB- or control-plane-backed provider can be swapped in later behind this seam without touching callers.
type CellProvider interface {
	Cells() ([]RegionCell, Keyring, error)
}

// RegionResolver maps a region + required capabilities to a compliant RegionCell, deterministically.
type RegionResolver struct {
	provider CellProvider
	now      func() time.Time
}

// NewRegionResolver returns a resolver over a provider (defaults clock to time.Now).
func NewRegionResolver(provider CellProvider) *RegionResolver {
	return &RegionResolver{provider: provider, now: time.Now}
}

// Resolve returns the lowest-id ATTESTED cell in region that satisfies every required capability. It is
// deterministic (stable id ordering) and fail-closed: unknown/empty region or no compliant cell -> error.
func (r *RegionResolver) Resolve(region string, required []string) (RegionCell, error) {
	reg := strings.ToUpper(strings.TrimSpace(region))
	if reg == "" {
		return RegionCell{}, fmt.Errorf("%w: empty region", ErrUnknownRegion)
	}
	cells, keys, err := r.provider.Cells()
	if err != nil {
		return RegionCell{}, err
	}
	now := r.now()
	var candidates []RegionCell
	for _, c := range cells {
		if strings.ToUpper(strings.TrimSpace(c.Region)) != reg {
			continue
		}
		if err := VerifyAttestation(c, keys, now); err != nil {
			continue // unattested/untrusted/expired cells are never selected
		}
		if !hasCapabilities(c.Capabilities, required) {
			continue
		}
		candidates = append(candidates, c)
	}
	if len(candidates) == 0 {
		return RegionCell{}, fmt.Errorf("%w: region %s for caps %v", ErrNoCompliantCell, reg, required)
	}
	sort.Slice(candidates, func(i, j int) bool { return candidates[i].ID < candidates[j].ID })
	return candidates[0], nil
}

func hasCapabilities(have, required []string) bool {
	set := make(map[string]struct{}, len(have))
	for _, h := range have {
		set[strings.ToLower(strings.TrimSpace(h))] = struct{}{}
	}
	for _, rq := range required {
		if _, ok := set[strings.ToLower(strings.TrimSpace(rq))]; !ok {
			return false
		}
	}
	return true
}

// StaticProvider is a CellProvider over an in-memory cell list + keyring (used for config load + tests).
type StaticProvider struct {
	CellList []RegionCell
	Keyring  Keyring
}

// Cells implements CellProvider.
func (p StaticProvider) Cells() ([]RegionCell, Keyring, error) { return p.CellList, p.Keyring, nil }

// ConfigProvider loads cells + keyring from the residency config files (config/residency-profiles/*).
type ConfigProvider struct {
	CellsPath   string
	KeyringPath string
}

// Cells implements CellProvider by reading the configured files (fail-closed on missing/invalid).
func (p ConfigProvider) Cells() ([]RegionCell, Keyring, error) {
	cells, err := LoadCells(p.CellsPath)
	if err != nil {
		return nil, nil, err
	}
	keys, err := LoadKeyring(p.KeyringPath)
	if err != nil {
		return nil, nil, err
	}
	return cells, keys, nil
}
