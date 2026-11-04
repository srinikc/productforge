package observe

import (
	"time"

	"productforge/edpsvc/internal/limits"
)

var stores = map[string]struct{}{
	"db": {}, "object": {}, "cache": {}, "queue": {},
}

// Recorder emits bounded per-store request, error, latency, and degradation metrics.
type Recorder struct {
	M *limits.Metrics
}

func allowed(store string) bool {
	_, ok := stores[store]
	return ok
}

// Request records one store operation outcome and latency.
func (r Recorder) Request(store, outcome string, d time.Duration) {
	if r.M == nil || !allowed(store) {
		return
	}
	r.M.Inc("edp_store_requests_total", "store", store, "outcome", outcome)
	ms := d.Milliseconds()
	if ms < 0 {
		ms = 0
	}
	r.M.Set("edp_store_latency_ms{store=\""+store+"\"}", int(ms))
}

// Degraded records the current degradation state for a store.
func (r Recorder) Degraded(store string, degraded bool) {
	if r.M == nil || !allowed(store) {
		return
	}
	v := 0
	if degraded {
		v = 1
	}
	r.M.Set("edp_store_degraded{store=\""+store+"\"}", v)
}
