package s3store

import (
	"testing"
	"time"

	"github.com/minio/minio-go/v7"
	"productforge/datastore"
)

func TestRetentionFor(t *testing.T) {
	if _, _, err := retentionFor(datastore.PutOptions{}); err != nil {
		t.Fatalf("zero retention must be a no-op: %v", err)
	}
	if _, _, err := retentionFor(datastore.PutOptions{Retention: time.Hour}); err == nil {
		t.Fatal("retention without Immutable must fail closed")
	}
	if _, _, err := retentionFor(datastore.PutOptions{Retention: time.Second, Immutable: true}); err == nil {
		t.Fatal("sub-minute retention must fail closed")
	}
	mode, until, err := retentionFor(datastore.PutOptions{Retention: time.Hour, Immutable: true})
	if err != nil || mode != minio.Governance || !until.After(time.Now()) {
		t.Fatalf("valid retention mapping wrong: %v %v %v", mode, until, err)
	}
	cmode, _, err := retentionFor(datastore.PutOptions{Retention: time.Hour, Immutable: true, RetentionMode: "COMPLIANCE", ComplianceOptIn: true})
	if err != nil || cmode != minio.Compliance {
		t.Fatalf("COMPLIANCE mapping wrong: %v %v", cmode, err)
	}
	if _, _, err := retentionFor(datastore.PutOptions{Retention: time.Hour, Immutable: true, RetentionMode: "bogus"}); err == nil {
		t.Fatal("unknown retention mode must fail closed")
	}
}
