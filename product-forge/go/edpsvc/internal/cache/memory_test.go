package cache

import (
	"context"
	"testing"
	"time"
)

func TestStoreSetGetDeleteAndExpiry(t *testing.T) {
	s := New()
	ctx := context.Background()
	now := time.Unix(100, 0)
	s.now = func() time.Time { return now }
	if err := s.Set(ctx, "k", []byte("v"), time.Second); err != nil {
		t.Fatal(err)
	}
	if v, ok, _ := s.Get(ctx, "k"); !ok || string(v) != "v" {
		t.Fatalf("get: %q %v", v, ok)
	}
	now = now.Add(2 * time.Second)
	if _, ok, _ := s.Get(ctx, "k"); ok {
		t.Fatal("expired entry returned")
	}
	_ = s.Set(ctx, "k2", []byte("v"), 0)
	if err := s.Delete(ctx, "k2"); err != nil {
		t.Fatal(err)
	}
	if _, ok, _ := s.Get(ctx, "k2"); ok {
		t.Fatal("deleted entry returned")
	}
}
