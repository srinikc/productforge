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
	// One SECURITY DEFINER probe: runtime roles can execute it without table grants.
	if err := pool.QueryRow(ctx, `SELECT months_ahead, lead_months, last_rotation_hours FROM audit_coverage_status()`).
		Scan(&st.MonthsAhead, &st.LeadMonths, &st.LastRotationAgeHours); err != nil {
		return st, err
	}
	st.Stale = maxAgeHours > 0 && (st.LastRotationAgeHours < 0 || st.LastRotationAgeHours > maxAgeHours)
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
