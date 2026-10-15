package s3store

import (
	"context"
	"os"
	"testing"

	"productforge/datastore"
)

func TestCapabilities(t *testing.T) {
	c := (&S3Store{}).Capabilities()
	if !c.SignedURLs || !c.ObjectVersioning || !c.MultipartUpload {
		t.Fatalf("capabilities = %+v", c)
	}
}

func TestNewRequiresEndpointAndBucket(t *testing.T) {
	if _, err := New(context.Background(), Config{}); err == nil {
		t.Fatal("expected error for empty config")
	}
}

func TestConformObjectStore_Integration(t *testing.T) {
	endpoint := os.Getenv("PF_S3_ENDPOINT")
	if endpoint == "" {
		t.Skip("set PF_S3_ENDPOINT (+ PF_S3_BUCKET/keys) to run the S3 conformance suite")
	}
	ctx := context.Background()
	s, err := New(ctx, Config{
		Endpoint:  endpoint,
		Bucket:    os.Getenv("PF_S3_BUCKET"),
		AccessKey: os.Getenv("PF_S3_ACCESS_KEY"),
		SecretKey: os.Getenv("PF_S3_SECRET_KEY"),
		Region:    os.Getenv("PF_S3_REGION"),
		UseSSL:    os.Getenv("PF_S3_USE_SSL") == "1",
		Ensure:    true,
	})
	if err != nil {
		t.Fatal(err)
	}
	if errs := datastore.ConformObjectStore(ctx, s); len(errs) != 0 {
		t.Fatalf("conformance failed: %v", errs)
	}
}
