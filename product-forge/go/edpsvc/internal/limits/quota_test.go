package limits

import (
	"testing"
	"time"
)

func quotaCfg() Config {
	c := DefaultConfig()
	c.TenantRPM = 100
	c.GlobalRPM = 1000
	c.TenantConcurrency = 10
	c.GlobalConcurrency = 10
	c.Pool.MaxConns = 10
	return c
}

func TestQuotaTenantRateAndRetryAfter(t *testing.T) {
	c := quotaCfg()
	c.TenantRPM = 2
	now := time.Unix(1000, 0)
	q := NewQuota(c, func() time.Time { return now }, NewMetrics())
	for i := 0; i < 2; i++ {
		d, release := q.Acquire("t1")
		if !d.Allowed {
			t.Fatalf("request %d denied: %+v", i, d)
		}
		release()
	}
	d, _ := q.Acquire("t1")
	if d.Allowed || d.Scope != "tenant" {
		t.Fatalf("want tenant denial, got %+v", d)
	}
	if d.RetryAfter < 29*time.Second || d.RetryAfter > 31*time.Second {
		t.Fatalf("want ~30s Retry-After, got %s", d.RetryAfter)
	}
	now = now.Add(30 * time.Second)
	d, release := q.Acquire("t1")
	if !d.Allowed {
		t.Fatalf("after refill want allowed, got %+v", d)
	}
	release()
}

func TestQuotaGlobalDenial(t *testing.T) {
	c := quotaCfg()
	c.GlobalRPM = 2
	c.TenantRPM = 10
	now := time.Unix(2000, 0)
	q := NewQuota(c, func() time.Time { return now }, NewMetrics())
	for _, tenant := range []string{"a", "b"} {
		d, release := q.Acquire(tenant)
		if !d.Allowed {
			t.Fatalf("%s denied: %+v", tenant, d)
		}
		release()
	}
	d, _ := q.Acquire("c")
	if d.Allowed || d.Scope != "global" {
		t.Fatalf("want global denial, got %+v", d)
	}
}

func TestQuotaConcurrencyRelease(t *testing.T) {
	c := quotaCfg()
	c.GlobalConcurrency = 2
	c.TenantConcurrency = 1
	q := NewQuota(c, nil, NewMetrics())
	d, release := q.Acquire("t")
	if !d.Allowed {
		t.Fatalf("first denied: %+v", d)
	}
	d2, release2 := q.Acquire("t")
	if d2.Allowed || d2.Scope != "tenant_concurrency" {
		t.Fatalf("want tenant_concurrency denial, got %+v", d2)
	}
	release2()
	release()
	d3, release3 := q.Acquire("t")
	if !d3.Allowed {
		t.Fatalf("after release want allowed, got %+v", d3)
	}
	release3()
}

func TestQuotaTenantCapAndIdleEviction(t *testing.T) {
	c := quotaCfg()
	c.MaxTenantBuckets = 1
	c.BucketIdleTTL = time.Minute
	now := time.Unix(3000, 0)
	q := NewQuota(c, func() time.Time { return now }, NewMetrics())
	d, rel := q.Acquire("a")
	if !d.Allowed {
		t.Fatal(d)
	}
	rel()
	d, _ = q.Acquire("b")
	if d.Allowed || d.Scope != "tenant_cap" {
		t.Fatalf("want tenant_cap denial, got %+v", d)
	}
	now = now.Add(2 * time.Minute)
	d, rel = q.Acquire("b")
	if !d.Allowed {
		t.Fatalf("want eviction to admit b, got %+v", d)
	}
	rel()
	if q.TenantBuckets() != 1 {
		t.Fatalf("want 1 tenant bucket, got %d", q.TenantBuckets())
	}
}

func TestQuotaClockSkewDoesNotMint(t *testing.T) {
	c := quotaCfg()
	c.TenantRPM = 1
	now := time.Unix(4000, 0)
	q := NewQuota(c, func() time.Time { return now }, NewMetrics())
	d, rel := q.Acquire("t")
	if !d.Allowed {
		t.Fatal(d)
	}
	rel()
	now = now.Add(-10 * time.Second)
	d, _ = q.Acquire("t")
	if d.Allowed {
		t.Fatal("backwards clock must not mint tokens")
	}
}
