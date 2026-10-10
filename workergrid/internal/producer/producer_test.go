package producer

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// BI-PF-1222: the epic scope must be forwarded to the producer's schedule/next call.
func TestNextForwardsEpicQuery(t *testing.T) {
	var gotQuery string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotQuery = r.URL.RawQuery
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"data":{"found":true,"item":"BI-PF-0393"}}`))
	}))
	defer srv.Close()

	data, ok := Next(srv.URL, "", "product_forge", "", "execute", "BI-PF-0390")
	if !ok {
		t.Fatalf("ok=false")
	}
	if data == nil {
		t.Fatalf("nil data")
	}
	for _, want := range []string{"scope=product_forge", "stage=execute", "epic=BI-PF-0390"} {
		if !strings.Contains(gotQuery, want) {
			t.Fatalf("query %q missing %q", gotQuery, want)
		}
	}
}

func TestNextOmitsEmptyEpic(t *testing.T) {
	var gotQuery string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotQuery = r.URL.RawQuery
		_, _ = w.Write([]byte(`{}`))
	}))
	defer srv.Close()

	if _, ok := Next(srv.URL, "", "product_forge", "", "", ""); !ok {
		t.Fatalf("ok=false")
	}
	if strings.Contains(gotQuery, "epic") {
		t.Fatalf("empty epic leaked into query: %q", gotQuery)
	}
}
