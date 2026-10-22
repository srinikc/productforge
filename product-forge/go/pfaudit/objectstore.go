package pfaudit

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

	"productforge/datastore"
	"productforge/objstore"
	"productforge/s3store"
)

// ObjectStore selects the archive backend from the environment: an S3-compatible bucket when
// PF_S3_ENDPOINT/PF_S3_BUCKET are set (with optional SSE-KMS), otherwise the local filesystem.
func ObjectStore(ctx context.Context) (datastore.ObjectStore, error) {
	bucket := os.Getenv("PF_S3_BUCKET")
	if bucket != "" || os.Getenv("PF_S3_ENDPOINT") != "" {
		return s3store.New(ctx, s3store.Config{
			Endpoint:  os.Getenv("PF_S3_ENDPOINT"),
			AccessKey: os.Getenv("PF_S3_ACCESS_KEY"),
			SecretKey: os.Getenv("PF_S3_SECRET_KEY"),
			Bucket:    bucket,
			Region:    os.Getenv("PF_S3_REGION"),
			UseSSL:    os.Getenv("PF_S3_USE_SSL") == "1",
			Ensure:    os.Getenv("PF_S3_ENSURE") == "1",
		})
	}
	root := os.Getenv("PF_OBJECT_ROOT")
	if root == "" {
		root = filepath.Join(os.TempDir(), "pfaudit-objects")
	}
	return objstore.NewLocalStore(root, 1<<34)
}

// DefaultSSE returns the server-side encryption to request for cold archives. It is empty for the local
// adapter (which rejects SSE) and defaults to AES256 whenever an S3 bucket is configured.
func DefaultSSE() string {
	if v := os.Getenv("PF_AUDIT_SSE"); v != "" {
		return v
	}
	if os.Getenv("PF_S3_BUCKET") != "" {
		return "AES256"
	}
	return ""
}

// CheckSSE fails fast when the configured backend cannot honour the requested encryption.
func CheckSSE(store datastore.ObjectStore, sse string) error {
	if sse == "" {
		return nil
	}
	if _, ok := store.(*s3store.S3Store); !ok {
		return fmt.Errorf("pfaudit: %q requested but backend %T cannot provide server-side encryption", sse, store)
	}
	return nil
}
