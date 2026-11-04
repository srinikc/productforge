package bench

import (
	"encoding/json"
	"fmt"
	"os"
)

// SLO is the per-group latency budget for a benchmark run.
type SLO struct {
	P95Ms    float64 `json:"p95_ms"`
	P99Ms    float64 `json:"p99_ms"`
	MaxError int     `json:"max_errors"`
}

// SLOConfig is the versioned benchmark budget document.
type SLOConfig struct {
	Version  int            `json:"version"`
	Defaults SLO            `json:"defaults"`
	Groups   map[string]SLO `json:"groups"`
}

// Violation is one failed benchmark comparison.
type Violation struct {
	Group    string  `json:"group"`
	Scenario string  `json:"scenario"`
	Metric   string  `json:"metric"`
	Actual   float64 `json:"actual"`
	Limit    float64 `json:"limit"`
}

func (v Violation) Error() string {
	return fmt.Sprintf("%s/%s %s=%.3f limit=%.3f", v.Group, v.Scenario, v.Metric, v.Actual, v.Limit)
}

// LoadSLO reads and validates an SLO config.
func LoadSLO(path string) (SLOConfig, error) {
	var c SLOConfig
	raw, err := os.ReadFile(path)
	if err != nil {
		return c, err
	}
	if err := json.Unmarshal(raw, &c); err != nil {
		return c, err
	}
	if c.Version < 1 || c.Defaults.P95Ms <= 0 || c.Defaults.P99Ms <= 0 {
		return c, fmt.Errorf("bench: invalid SLO config")
	}
	return c, nil
}

// Compare returns all benchmark results that exceed their group/default budget.
func Compare(rep Report, c SLOConfig) []Violation {
	var out []Violation
	for _, r := range rep.Results {
		limit := c.Defaults
		if g, ok := c.Groups[r.Group]; ok {
			if g.P95Ms > 0 {
				limit.P95Ms = g.P95Ms
			}
			if g.P99Ms > 0 {
				limit.P99Ms = g.P99Ms
			}
			if g.MaxError != 0 {
				limit.MaxError = g.MaxError
			}
		}
		if r.Err != "" {
			out = append(out, Violation{Group: r.Group, Scenario: r.Scenario, Metric: "errors", Actual: 1, Limit: float64(limit.MaxError)})
			continue
		}
		if r.P95Ms > limit.P95Ms {
			out = append(out, Violation{Group: r.Group, Scenario: r.Scenario, Metric: "p95_ms", Actual: r.P95Ms, Limit: limit.P95Ms})
		}
		if r.P99Ms > limit.P99Ms {
			out = append(out, Violation{Group: r.Group, Scenario: r.Scenario, Metric: "p99_ms", Actual: r.P99Ms, Limit: limit.P99Ms})
		}
	}
	return out
}
