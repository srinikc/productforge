package pfaudit

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"
)

// CoverageStatus is the startup/cron view of partition coverage: the AC requires the service and the ops
// cron to surface months_ahead/low-coverage non-fatally, and to alert when rotation has gone stale.
type CoverageStatus struct {
	Coverage
	LeadMonths           int
	LastRotationAgeHours float64 // < 0 when no rotation has ever run
	Stale                bool
}

// Low reports whether coverage is below the configured lead time.
func (c CoverageStatus) Low() bool { return c.MonthsAhead < c.LeadMonths }

// CheckCoverage reads coverage + lead time + the last recorded rotation event. It never fails on a stale
// job: callers decide whether to alert (AC: surface non-fatally).
func CheckCoverage(ctx context.Context, pool *pgxpool.Pool, maxAgeHours float64) (CoverageStatus, error) {
	var st CoverageStatus
	cov, err := ReadCoverage(ctx, pool)
	if err != nil {
		return st, err
	}
	st.Coverage = cov
	if err := pool.QueryRow(ctx, `SELECT lead_months FROM audit_partition_config WHERE id`).Scan(&st.LeadMonths); err != nil {
		return st, err
	}
	var age *float64
	if err := pool.QueryRow(ctx, `SELECT EXTRACT(EPOCH FROM (now() - max(at)))/3600
		FROM audit_migration_state_events
		WHERE to_state IN ('archived', 'dropped', 'purged')`).Scan(&age); err != nil {
		return st, err
	}
	if age == nil {
		st.LastRotationAgeHours = -1
		st.Stale = true
	} else {
		st.LastRotationAgeHours = *age
		st.Stale = maxAgeHours > 0 && *age > maxAgeHours
	}
	return st, nil
}

// EmitCoverage records the AC metrics; stale coverage is a warning, never a hard failure.
func EmitCoverage(m *Metrics, st CoverageStatus) {
	m.Gauge(MetricMonthsAhead, float64(st.MonthsAhead))
	if st.Low() {
		m.Inc(MetricLowCoverage)
	}
	stale := 0.0
	if st.Stale {
		stale = 1
	}
	m.Gauge(MetricRotationStale, stale)
}
