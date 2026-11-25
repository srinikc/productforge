package observe

import (
	"strings"
	"testing"
	"time"

	"productforge/edpsvc/internal/limits"
)

func TestRecorderBoundedStores(t *testing.T) {
	m := limits.NewMetrics()
	r := Recorder{M: m}
	for _, s := range []string{"db", "object", "cache", "queue"} {
		r.Request(s, "ok", 5*time.Millisecond)
		r.Degraded(s, true)
	}
	r.Request("tenant-a", "ok", time.Millisecond)
	r.Request("db", "tenant-a", time.Millisecond)
	var b strings.Builder
	m.Write(&b)
	out := b.String()
	for _, s := range []string{"db", "object", "cache", "queue"} {
		if !strings.Contains(out, `store="`+s+`"`) {
			t.Fatalf("missing store %s: %s", s, out)
		}
	}
	if strings.Contains(out, "tenant-a") {
		t.Fatalf("unbounded store label leaked: %s", out)
	}
}
