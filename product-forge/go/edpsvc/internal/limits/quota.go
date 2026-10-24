package limits

import (
	"math"
	"sync"
	"time"
)

// Clock is injectable for deterministic Retry-After tests.
type Clock func() time.Time

// Decision is a quota decision.
type Decision struct {
	Allowed    bool
	RetryAfter time.Duration
	Scope      string // global | tenant | concurrency
}

type bucket struct {
	tokens float64
	last   time.Time
	seen   time.Time
}

// Quota enforces per-tenant + global token buckets and concurrency caps in-process.
type Quota struct {
	cfg     Config
	now     Clock
	metrics *Metrics
	mu      sync.Mutex
	global  bucket
	tenants map[string]*bucket
	gSem    chan struct{}
	tSems   map[string]chan struct{}
}

// NewQuota builds the quota state. A nil clock uses time.Now.
func NewQuota(cfg Config, clock Clock, m *Metrics) *Quota {
	if clock == nil {
		clock = time.Now
	}
	q := &Quota{cfg: cfg, now: clock, metrics: m, tenants: map[string]*bucket{},
		gSem: make(chan struct{}, cfg.GlobalConcurrency), tSems: map[string]chan struct{}{}}
	now := clock()
	q.global = bucket{tokens: float64(cfg.GlobalRPM), last: now, seen: now}
	return q
}

func refill(b *bucket, capacity, perSecond float64, now time.Time) {
	elapsed := now.Sub(b.last).Seconds()
	if elapsed <= 0 { // clock skew/backwards: never mint tokens, just re-anchor
		b.last = now
		return
	}
	b.tokens = math.Min(capacity, b.tokens+elapsed*perSecond)
	b.last = now
}

func (q *Quota) take(b *bucket, capacity, perSecond float64, now time.Time) (bool, time.Duration) {
	refill(b, capacity, perSecond, now)
	if b.tokens >= 1 {
		b.tokens--
		b.seen = now
		return true, 0
	}
	need := (1 - b.tokens) / perSecond
	wait := time.Duration(math.Ceil(need)) * time.Second
	if wait < time.Second {
		wait = time.Second
	}
	return false, wait
}

func (q *Quota) refund(b *bucket, capacity float64) {
	b.tokens = math.Min(capacity, b.tokens+1)
}

func (q *Quota) tenantBucket(tenant string, now time.Time) *bucket {
	if b, ok := q.tenants[tenant]; ok {
		return b
	}
	if len(q.tenants) >= q.cfg.MaxTenantBuckets {
		for name, b := range q.tenants {
			if now.Sub(b.seen) >= q.cfg.BucketIdleTTL {
				delete(q.tenants, name)
				delete(q.tSems, name)
				if q.metrics != nil {
					q.metrics.Inc("edp_quota_evictions_total")
					q.metrics.Set("edp_quota_tenant_buckets", len(q.tenants))
				}
			}
		}
		if len(q.tenants) >= q.cfg.MaxTenantBuckets {
			return nil // fail closed: no room for a new tenant
		}
	}
	b := &bucket{tokens: float64(q.cfg.TenantRPM), last: now, seen: now}
	q.tenants[tenant] = b
	q.tSems[tenant] = make(chan struct{}, q.cfg.TenantConcurrency)
	if q.metrics != nil {
		q.metrics.Set("edp_quota_tenant_buckets", len(q.tenants))
	}
	return b
}

// Acquire admits a request for tenant (empty = global only). On success the returned release func MUST be
// called (defer) to free the concurrency slots.
func (q *Quota) Acquire(tenant string) (Decision, func()) {
	now := q.now()
	q.mu.Lock()
	defer q.mu.Unlock()

	if ok, wait := q.take(&q.global, float64(q.cfg.GlobalRPM), float64(q.cfg.GlobalRPM)/60.0, now); !ok {
		if q.metrics != nil {
			q.metrics.Inc("edp_quota_denials_total", "scope", "global")
		}
		return Decision{Allowed: false, RetryAfter: wait, Scope: "global"}, func() {}
	}
	var tb *bucket
	if tenant != "" {
		tb = q.tenantBucket(tenant, now)
		if tb == nil {
			q.refund(&q.global, float64(q.cfg.GlobalRPM))
			if q.metrics != nil {
				q.metrics.Inc("edp_quota_denials_total", "scope", "tenant_cap")
			}
			return Decision{Allowed: false, RetryAfter: time.Second, Scope: "tenant_cap"}, func() {}
		}
	}
	if tb != nil {
		if ok, wait := q.take(tb, float64(q.cfg.TenantRPM), float64(q.cfg.TenantRPM)/60.0, now); !ok {
			q.refund(&q.global, float64(q.cfg.GlobalRPM))
			if q.metrics != nil {
				q.metrics.Inc("edp_quota_denials_total", "scope", "tenant")
			}
			return Decision{Allowed: false, RetryAfter: wait, Scope: "tenant"}, func() {}
		}
	}

	select {
	case q.gSem <- struct{}{}:
	default:
		q.refund(&q.global, float64(q.cfg.GlobalRPM))
		if tb != nil {
			q.refund(tb, float64(q.cfg.TenantRPM))
		}
		if q.metrics != nil {
			q.metrics.Inc("edp_quota_denials_total", "scope", "global_concurrency")
		}
		return Decision{Allowed: false, RetryAfter: time.Second, Scope: "global_concurrency"}, func() {}
	}
	var tSem chan struct{}
	if tb != nil {
		tSem = q.tSems[tenant]
		select {
		case tSem <- struct{}{}:
		default:
			<-q.gSem
			q.refund(&q.global, float64(q.cfg.GlobalRPM))
			q.refund(tb, float64(q.cfg.TenantRPM))
			if q.metrics != nil {
				q.metrics.Inc("edp_quota_denials_total", "scope", "tenant_concurrency")
			}
			return Decision{Allowed: false, RetryAfter: time.Second, Scope: "tenant_concurrency"}, func() {}
		}
	}
	var once sync.Once
	release := func() {
		once.Do(func() {
			<-q.gSem
			if tSem != nil {
				<-tSem
			}
		})
	}
	if q.metrics != nil {
		q.metrics.Inc("edp_quota_allowed_total")
	}
	return Decision{Allowed: true}, release
}

// TenantBuckets reports the current bucket count (admin/limits).
func (q *Quota) TenantBuckets() int {
	q.mu.Lock()
	defer q.mu.Unlock()
	return len(q.tenants)
}
