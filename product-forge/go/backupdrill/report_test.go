package backupdrill

import (
	"testing"
	"time"
)

func TestReportFreshness(t *testing.T) {
	dir := t.TempDir()
	if err := CheckFreshness(dir, []string{"full"}, time.Hour); err == nil {
		t.Fatal("missing report must fail")
	}
	if _, err := SaveReport(dir, "full", true, map[string]string{"k": "v"}); err != nil {
		t.Fatal(err)
	}
	if err := CheckFreshness(dir, []string{"full"}, time.Hour); err != nil {
		t.Fatalf("fresh report rejected: %v", err)
	}
	if _, err := SaveReport(dir, "tenant", false, map[string]string{}); err != nil {
		t.Fatal(err)
	}
	if err := CheckFreshness(dir, []string{"tenant"}, time.Hour); err == nil {
		t.Fatal("failed report must fail freshness")
	}
}
