package limits

import (
	"strings"
	"testing"
	"time"
)

func TestMetricsExposition(t *testing.T) {
	m := NewMetrics()
	m.Inc("edp_quota_denials_total", "scope", "global")
	m.Inc("edp_quota_denials_total", "scope", "global")
	m.Set("edp_quota_tenant_buckets", 3)
	m.Observe("upload", 413, 120*time.Millisecond)
	var b strings.Builder
	m.Write(&b)
	out := b.String()
	for _, want := range []string{
		`edp_quota_denials_total{scope="global"} 2`,
		"edp_quota_tenant_buckets 3",
		`edp_http_requests_total{class="upload",status="413"} 1`,
		`edp_http_request_duration_seconds_bucket{class="upload",le="0.25"} 1`,
		`edp_http_request_duration_seconds_count{class="upload"} 1`,
	} {
		if !strings.Contains(out, want) {
			t.Fatalf("missing %q in:\n%s", want, out)
		}
	}
}
