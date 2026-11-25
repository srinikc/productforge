// Command objreconcile is the drift job entrypoint for EDP-16.
//
// It compares a manifest JSON file with the object store (local root or S3 from env) and prints a
// deterministic report; exit 1 when drift is detected.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"productforge/datastore"
	"productforge/objreconcile"
	"productforge/objstore"
	"productforge/s3store"
)

func storeFromEnv(ctx context.Context, root string) (datastore.ObjectStore, error) {
	if os.Getenv("PF_S3_ENDPOINT") != "" || os.Getenv("PF_S3_BUCKET") != "" {
		return s3store.New(ctx, s3store.Config{
			Endpoint: os.Getenv("PF_S3_ENDPOINT"), AccessKey: os.Getenv("PF_S3_ACCESS_KEY"),
			SecretKey: os.Getenv("PF_S3_SECRET_KEY"), Bucket: os.Getenv("PF_S3_BUCKET"),
			Region: os.Getenv("PF_S3_REGION"), UseSSL: os.Getenv("PF_S3_USE_SSL") == "1",
		})
	}
	if root == "" {
		root = os.Getenv("PF_OBJECT_ROOT")
	}
	if root == "" {
		return nil, fmt.Errorf("set PF_OBJECT_ROOT or the S3 environment")
	}
	return objstore.NewLocalStore(root, 0)
}

func main() {
	var manifestPath, prefix, root string
	flag.StringVar(&manifestPath, "manifest", "", "manifest JSON (array or {objects:[...]})")
	flag.StringVar(&prefix, "prefix", "", "object key prefix")
	flag.StringVar(&root, "root", "", "local object root (default PF_OBJECT_ROOT)")
	flag.Parse()
	if manifestPath == "" {
		fmt.Fprintln(os.Stderr, "objreconcile: --manifest is required")
		os.Exit(2)
	}
	raw, err := os.ReadFile(manifestPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "objreconcile:", err)
		os.Exit(2)
	}
	var entries []objreconcile.Entry
	var wrapped struct {
		Objects []objreconcile.Entry `json:"objects"`
	}
	if err := json.Unmarshal(raw, &entries); err != nil {
		if err2 := json.Unmarshal(raw, &wrapped); err2 != nil {
			fmt.Fprintln(os.Stderr, "objreconcile: manifest is neither an array nor {objects:[]}:", err)
			os.Exit(2)
		}
		entries = wrapped.Objects
	}
	ctx := context.Background()
	st, err := storeFromEnv(ctx, root)
	if err != nil {
		fmt.Fprintln(os.Stderr, "objreconcile:", err)
		os.Exit(2)
	}
	rep, err := objreconcile.Scan(ctx, st, prefix, entries)
	if err != nil {
		fmt.Fprintln(os.Stderr, "objreconcile:", err)
		os.Exit(2)
	}
	out, _ := json.MarshalIndent(rep, "", "  ")
	fmt.Println(string(out))
	if !rep.Clean() {
		os.Exit(1)
	}
}
