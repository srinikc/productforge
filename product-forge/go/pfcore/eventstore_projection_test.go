package main

import (
	"path/filepath"
	"testing"
)

func TestProjectionPathDefault(t *testing.T) {
	t.Setenv("PF_EVENT_PROJECTION_DIR", "")
	if got, want := projectionPath("t1"), filepath.Join("products", "t1", "events.jsonl"); got != want {
		t.Fatalf("got %q want %q", got, want)
	}
}

func TestProjectionPathEnv(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("PF_EVENT_PROJECTION_DIR", dir)
	if got, want := projectionPath("t1"), filepath.Join(dir, "t1", "events.jsonl"); got != want {
		t.Fatalf("got %q want %q", got, want)
	}
}
