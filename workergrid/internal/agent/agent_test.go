package agent

import (
	"context"
	"errors"
	"runtime"
	"strings"
	"testing"
	"time"
)

func TestExpandSubstitutesAndQuotes(t *testing.T) {
	out := expand(`run {item_id} at {worktree} on {branch}`, map[string]string{
		"item_id": "BI-1", "worktree": "C:/a b/wt", "branch": "wg/bi-1",
	})
	if strings.Contains(out, "{") {
		t.Fatalf("placeholders left: %q", out)
	}
	for _, want := range []string{"BI-1", "C:/a b/wt", "wg/bi-1"} {
		if !strings.Contains(out, want) {
			t.Fatalf("missing %q in %q", want, out)
		}
	}
	if runtime.GOOS == "windows" {
		if !strings.Contains(out, `"C:/a b/wt"`) {
			t.Fatalf("windows value not double-quoted: %q", out)
		}
	} else if !strings.Contains(out, `'C:/a b/wt'`) {
		t.Fatalf("unix value not single-quoted: %q", out)
	}
}

func TestShellQuoteEscapes(t *testing.T) {
	if runtime.GOOS == "windows" {
		if got := shellQuote(`say "hi"`); got != `"say 'hi'"` {
			t.Fatalf("windows quote: %q", got)
		}
		return
	}
	if got := shellQuote("it's"); got != `'it'\''s'` {
		t.Fatalf("unix quote: %q", got)
	}
}

func TestExitCode(t *testing.T) {
	if got := exitCode(nil); got != 0 {
		t.Fatalf("nil -> %d", got)
	}
	if got := exitCode(errors.New("boom")); got != -1 {
		t.Fatalf("generic error -> %d", got)
	}
}

func TestLastLine(t *testing.T) {
	if got := lastLine("a\nb\n"); got != "b" {
		t.Fatalf("got %q", got)
	}
	if got := lastLine(""); got != "" {
		t.Fatalf("empty -> %q", got)
	}
}

func TestCapWriterKeepsTail(t *testing.T) {
	w := &capWriter{limit: 4}
	_, _ = w.Write([]byte("abcdef"))
	_, _ = w.Write([]byte("gh"))
	if got := w.String(); got != "efgh" {
		t.Fatalf("tail: %q", got)
	}
}

func TestTruthy(t *testing.T) {
	cases := []struct {
		in   any
		want bool
	}{
		{nil, false}, {"", false}, {"x", true}, {float64(0), false}, {float64(2), true},
		{false, false}, {true, true}, {[]any{}, false}, {[]any{1}, true},
		{map[string]any{}, false}, {map[string]any{"a": 1}, true},
	}
	for _, c := range cases {
		if got := truthy(c.in); got != c.want {
			t.Fatalf("truthy(%v) = %v, want %v", c.in, got, c.want)
		}
	}
}

func TestWithTimeout(t *testing.T) {
	ctx, cancel := withTimeout(context.Background(), 0)
	defer cancel()
	if _, ok := ctx.Deadline(); ok {
		t.Fatal("secs=0 must not set a deadline")
	}
	ctx2, cancel2 := withTimeout(context.Background(), 1)
	defer cancel2()
	if dl, ok := ctx2.Deadline(); !ok || time.Until(dl) > time.Minute {
		t.Fatal("secs=1 must set a ~1s deadline")
	}
}
