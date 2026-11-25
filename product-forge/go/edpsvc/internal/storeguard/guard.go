package storeguard

import (
	"errors"
	"fmt"
	"time"

	"productforge/edpsvc/internal/degrade"
	"productforge/edpsvc/internal/limits"
	"productforge/edpsvc/internal/observe"
)

var ErrQuota = errors.New("store quota denied")

// Guard applies degradation and quota policy at a store boundary and records bounded metrics.
type Guard struct {
	Quota   *limits.Quota
	Degrade degrade.Checker
	Metrics observe.Recorder
	Meter   *limits.Metrics
	Now     func() time.Time
}

// Do runs fn only after degradation and quota checks. A nil guard is a no-op wrapper.
func (g *Guard) Do(store, tenant string, fn func() error) error {
	if g == nil {
		return fn()
	}
	now := time.Now()
	if g.Now != nil {
		now = g.Now()
	}
	if err := g.Degrade.Check(store, now); err != nil {
		g.Metrics.Degraded(store, true)
		g.Metrics.Request(store, "degraded", 0)
		return err
	}
	g.Metrics.Degraded(store, false)
	if g.Quota != nil && tenant != "" {
		d, release := g.Quota.AcquireTenant(tenant)
		if !d.Allowed {
			if g.Meter != nil {
				g.Meter.Inc("edp_quota_denials_total", "store", store, "scope", d.Scope)
			}
			g.Metrics.Request(store, "denied", 0)
			return fmt.Errorf("%w: %s", ErrQuota, d.Scope)
		}
		if g.Meter != nil {
			g.Meter.Inc("edp_quota_allowed_total", "store", store)
		}
		defer release()
	}
	start := time.Now()
	err := fn()
	outcome := "ok"
	if err != nil {
		outcome = "error"
	}
	g.Metrics.Request(store, outcome, time.Since(start))
	return err
}
