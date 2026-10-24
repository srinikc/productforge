package limits

import (
	"fmt"
	"io"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

var histBuckets = []float64{0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120}

type histogram struct {
	class  string
	counts []int64
	sum    float64
	count  int64
}

// Metrics is a tiny dependency-free Prometheus exposition (counters, gauges, request-duration histograms).
type Metrics struct {
	mu       sync.Mutex
	counters map[string]float64
	gauges   map[string]float64
	hists    map[string]*histogram
}

// NewMetrics returns an empty registry.
func NewMetrics() *Metrics {
	return &Metrics{counters: map[string]float64{}, gauges: map[string]float64{}, hists: map[string]*histogram{}}
}

func labelKey(name string, labels ...string) string {
	if len(labels) == 0 {
		return name
	}
	var b strings.Builder
	b.WriteString(name)
	b.WriteString("{")
	for i := 0; i+1 < len(labels); i += 2 {
		if i > 0 {
			b.WriteString(",")
		}
		b.WriteString(labels[i])
		b.WriteString("=\"")
		b.WriteString(strings.ReplaceAll(labels[i+1], "\"", "\\\""))
		b.WriteString("\"")
	}
	b.WriteString("}")
	return b.String()
}

// Inc increments a labeled counter.
func (m *Metrics) Inc(name string, labels ...string) {
	if m == nil {
		return
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	m.counters[labelKey(name, labels...)]++
}

// Set records a gauge value.
func (m *Metrics) Set(name string, v int) {
	if m == nil {
		return
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	m.gauges[name] = float64(v)
}

// Observe records one request duration for a path class ("json"/"upload") and status.
func (m *Metrics) Observe(class string, status int, d time.Duration) {
	if m == nil {
		return
	}
	m.Inc("edp_http_requests_total", "class", class, "status", strconv.Itoa(status))
	m.Inc("edp_http_status_total", "status", strconv.Itoa(status))
	m.mu.Lock()
	defer m.mu.Unlock()
	h := m.hists[class]
	if h == nil {
		h = &histogram{class: class, counts: make([]int64, len(histBuckets))}
		m.hists[class] = h
	}
	sec := d.Seconds()
	h.count++
	h.sum += sec
	for i, b := range histBuckets {
		if sec <= b {
			h.counts[i]++
		}
	}
}

// Write emits the Prometheus text exposition (deterministic order).
func (m *Metrics) Write(w io.Writer) {
	if m == nil {
		return
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	keys := make([]string, 0, len(m.counters))
	for k := range m.counters {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		fmt.Fprintf(w, "%s %s\n", k, strconv.FormatFloat(m.counters[k], 'f', -1, 64))
	}
	gkeys := make([]string, 0, len(m.gauges))
	for k := range m.gauges {
		gkeys = append(gkeys, k)
	}
	sort.Strings(gkeys)
	for _, k := range gkeys {
		fmt.Fprintf(w, "%s %s\n", k, strconv.FormatFloat(m.gauges[k], 'f', -1, 64))
	}
	hkeys := make([]string, 0, len(m.hists))
	for k := range m.hists {
		hkeys = append(hkeys, k)
	}
	sort.Strings(hkeys)
	for _, class := range hkeys {
		h := m.hists[class]
		for i, b := range histBuckets {
			fmt.Fprintf(w, "edp_http_request_duration_seconds_bucket{class=%q,le=%q} %d\n",
				class, strconv.FormatFloat(b, 'f', -1, 64), h.counts[i])
		}
		fmt.Fprintf(w, "edp_http_request_duration_seconds_bucket{class=%q,le=\"+Inf\"} %d\n", class, h.count)
		fmt.Fprintf(w, "edp_http_request_duration_seconds_count{class=%q} %d\n", class, h.count)
		fmt.Fprintf(w, "edp_http_request_duration_seconds_sum{class=%q} %s\n",
			class, strconv.FormatFloat(h.sum, 'f', -1, 64))
	}
}
