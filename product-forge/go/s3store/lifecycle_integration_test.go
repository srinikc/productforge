package s3store

import (
	"context"
	"os"
	"strings"
	"testing"
	"time"

	"productforge/datastore"
)

// TestLifecycleConformance exercises object retention/legal hold against a real S3-compatible endpoint.
// It self-skips unless PF_S3_ENDPOINT + PF_S3_BUCKET are configured (the bucket must have object lock enabled).
func TestLifecycleConformance(t *testing.T) {
	if os.Getenv("PF_S3_ENDPOINT") == "" || os.Getenv("PF_S3_BUCKET") == "" {
		t.Skip("set PF_S3_ENDPOINT and PF_S3_BUCKET (object-lock enabled) to run the S3 lifecycle test")
	}
	ctx := context.Background()
	st, err := New(ctx, Config{
		Endpoint: os.Getenv("PF_S3_ENDPOINT"), AccessKey: os.Getenv("PF_S3_ACCESS_KEY"),
		SecretKey: os.Getenv("PF_S3_SECRET_KEY"), Bucket: os.Getenv("PF_S3_BUCKET"),
		Region: os.Getenv("PF_S3_REGION"), UseSSL: os.Getenv("PF_S3_USE_SSL") == "1",
	})
	if err != nil {
		t.Fatal(err)
	}
	key := "lifecycle-test/" + time.Now().UTC().Format("20060102T150405.000000000")
	if _, err := st.Put(ctx, key, strings.NewReader("x"), 1, datastore.PutOptions{Immutable: true}); err != nil {
		t.Fatalf("put: %v", err)
	}
	defer st.Delete(ctx, key, "")
	if err := st.ApplyLifecycle(ctx, key, "", datastore.LifecyclePolicy{
		Mode: "GOVERNANCE", RetainUntil: time.Now().Add(time.Hour), LegalHold: true,
	}); err != nil {
		t.Fatalf("apply lifecycle: %v", err)
	}
	state, err := st.ObjectLifecycle(ctx, key, "")
	if err != nil {
		t.Fatalf("read lifecycle: %v", err)
	}
	if !strings.EqualFold(state.Mode, "GOVERNANCE") || !state.LegalHold {
		t.Fatalf("lifecycle state = %+v", state)
	}
	if err := st.ApplyLifecycle(ctx, key, "", datastore.LifecyclePolicy{ReleaseLegalHold: true}); err != nil {
		t.Fatalf("release legal hold: %v", err)
	}
}
