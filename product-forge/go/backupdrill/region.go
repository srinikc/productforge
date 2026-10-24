package backupdrill

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

// RegionPolicy maps a tenant to its home cell; Default is used when the tenant is not listed.
type RegionPolicy struct {
	Cells   map[string]string `json:"cells"`
	Default string            `json:"default"`
}

func LoadRegionPolicy(path string) (RegionPolicy, error) {
	var p RegionPolicy
	b, err := os.ReadFile(path)
	if err != nil {
		return p, err
	}
	if err := json.Unmarshal(b, &p); err != nil {
		return p, err
	}
	return p, nil
}

// GuardRestore refuses a cross-region restore unless explicitly allowed with a reason.
func GuardRestore(tenant, target string, p RegionPolicy, allow bool, reason string) error {
	home := p.Cells[tenant]
	if home == "" {
		home = p.Default
	}
	if home == "" {
		return fmt.Errorf("backupdrill: no home region for tenant %q (fail closed)", tenant)
	}
	if strings.EqualFold(home, target) {
		return nil
	}
	if allow && strings.TrimSpace(reason) != "" {
		return nil
	}
	return fmt.Errorf("backupdrill: tenant %q belongs to %s, target %s refused (use --allow-cross-region --reason)", tenant, home, target)
}
