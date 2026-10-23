package pfaudit

import (
	"sync"
	"sync/atomic"
)

// Metric names are stable so dashboards/alerts can be wired without code changes.
const (
	MetricMonthsAhead       = "audit_partition_months_ahead"
	MetricLowCoverage       = "audit_partition_low_coverage_total"
	MetricRotationStale     = "audit_rotation_stale_total"
	MetricInsertOutOfRange  = "audit_insert_out_of_range_total"
	MetricProvisionSeconds  = "audit_provision_seconds"
	MetricSwapFreeze        = "audit_swap_freeze_seconds"
	MetricSwapRetry         = "audit_swap_retry_total"
	MetricSwapRetryExhaust  = "audit_swap_retry_exhausted_total"
	MetricCopyResumed       = "audit_copy_batch_resumed_total"
	MetricExport            = "audit_export_total"
	MetricDrop              = "audit_drop_total"
	MetricPurge             = "audit_purge_total"
	MetricHoldExtract       = "audit_hold_extract_total"
	MetricHoldExtractFailed = "audit_hold_extract_failed_total"
	MetricLateInsert        = "audit_late_insert_total"
	MetricHoldAfterPurge    = "audit_hold_after_purge_total"
	MetricPurgeBlockedHold  = "audit_purge_blocked_hold_total"
	MetricHoldUnarchived    = "audit_hold_unarchived_total"
	MetricAttachUnhardened  = "audit_attach_unhardened_total"
)

// Metrics is a tiny dependency-free registry: counters plus the latest gauge values. The CLIs render it
// as one structured JSON line (ops scrapes the process log), so no Prometheus dependency is introduced.
type Metrics struct {
	mu       sync.Mutex
	counters map[string]*int64
	gauges   map[string]float64
}

// NewMetrics returns an empty registry.
func NewMetrics() *Metrics {
	return &Metrics{counters: map[string]*int64{}, gauges: map[string]float64{}}
}

// Inc increments a counter (created on first use).
func (m *Metrics) Inc(name string) {
	m.mu.Lock()
	c, ok := m.counters[name]
	if !ok {
		c = new(int64)
		m.counters[name] = c
	}
	m.mu.Unlock()
	atomic.AddInt64(c, 1)
}

// Gauge sets a gauge value.
func (m *Metrics) Gauge(name string, v float64) {
	m.mu.Lock()
	m.gauges[name] = v
	m.mu.Unlock()
}

// Snapshot returns counters and gauges for rendering.
func (m *Metrics) Snapshot() (map[string]int64, map[string]float64) {
	m.mu.Lock()
	defer m.mu.Unlock()
	c := make(map[string]int64, len(m.counters))
	for k, v := range m.counters {
		c[k] = atomic.LoadInt64(v)
	}
	g := make(map[string]float64, len(m.gauges))
	for k, v := range m.gauges {
		g[k] = v
	}
	return c, g
}
