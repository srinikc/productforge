package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"github.com/jackc/pgx/v5"
	"time"

	"productforge/backupdrill"
	"productforge/datastore"
	"productforge/objstore"
	"productforge/s3store"
)

func storeFromEnv(ctx context.Context) (datastore.ObjectStore, error) {
	if os.Getenv("PF_S3_ENDPOINT") != "" || os.Getenv("PF_S3_BUCKET") != "" {
		return s3store.New(ctx, s3store.Config{
			Endpoint: os.Getenv("PF_S3_ENDPOINT"), AccessKey: os.Getenv("PF_S3_ACCESS_KEY"),
			SecretKey: os.Getenv("PF_S3_SECRET_KEY"), Bucket: os.Getenv("PF_S3_BUCKET"),
			Region: os.Getenv("PF_S3_REGION"), UseSSL: os.Getenv("PF_S3_USE_SSL") == "1",
		})
	}
	root := os.Getenv("PF_OBJECT_ROOT")
	if root == "" {
		return nil, fmt.Errorf("set PF_OBJECT_ROOT or the S3 environment")
	}
	return objstore.NewLocalStore(root, 0)
}

func main() {
	var (
		dsn, command, scratch, tenant, policy, target, reason, prefix string
		rtoSeconds                                                    float64
		repair, allowCross                                            bool
	)
	flag.StringVar(&dsn, "dsn", os.Getenv("PF_DB_DSN"), "PostgreSQL DSN")
	flag.StringVar(&command, "command", "", "pitr|full|tenant|reconcile|region")
	flag.StringVar(&scratch, "scratch", "pf_backup_drill", "scratch database name")
	flag.StringVar(&tenant, "tenant", "", "tenant id")
	flag.StringVar(&policy, "region-policy", "config/residency-policy.json", "region policy JSON")
	flag.StringVar(&target, "target", "", "target region cell")
	flag.StringVar(&reason, "reason", "", "cross-region reason")
	flag.StringVar(&prefix, "prefix", "", "object key prefix")
	flag.Float64Var(&rtoSeconds, "rto-seconds", 900, "RTO budget")
	flag.BoolVar(&repair, "repair", false, "delete metadata rows whose object is missing")
	flag.BoolVar(&allowCross, "allow-cross-region", false, "allow a cross-region restore with --reason")
	flag.Parse()
	if dsn == "" {
		fmt.Fprintln(os.Stderr, "pfbackupdrill: --dsn or PF_DB_DSN is required")
		os.Exit(2)
	}
	ctx := context.Background()
	out := func(v any, code int) {
		b, _ := json.MarshalIndent(v, "", "  ")
		fmt.Println(string(b))
		os.Exit(code)
	}
	switch command {
	case "region":
		p, err := backupdrill.LoadRegionPolicy(policy)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		if err := backupdrill.GuardRestore(tenant, target, p, allowCross, reason); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		out(map[string]string{"tenant": tenant, "target": target, "status": "allowed"}, 0)
	case "pitr":
		conn, err := pgx.Connect(ctx, dsn)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		defer conn.Close(ctx)
		r, err := backupdrill.CheckPITR(ctx, conn)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		code := 0
		if !r.OK {
			code = 1
		}
		out(r, code)
	case "full":
		r, err := backupdrill.FullRestore(ctx, dsn, scratch, timeSeconds(rtoSeconds))
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			out(r, 1)
		}
		out(r, 0)
	case "tenant":
		if tenant == "" {
			fmt.Fprintln(os.Stderr, "pfbackupdrill: --tenant is required")
			os.Exit(2)
		}
		r, err := backupdrill.TenantRestore(ctx, dsn, tenant, scratch)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			out(r, 1)
		}
		out(r, 0)
	case "reconcile":
		conn, err := pgx.Connect(ctx, dsn)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		defer conn.Close(ctx)
		st, err := storeFromEnv(ctx)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		rows, err := backupdrill.MetadataRows(ctx, conn)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		objects, err := st.List(ctx, prefix)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		d := backupdrill.Classify(rows, objects, prefix)
		var repaired int64
		if repair && len(d.Missing) > 0 {
			repaired, err = backupdrill.RepairMissing(ctx, conn, rows, d)
			if err != nil {
				fmt.Fprintln(os.Stderr, err)
				os.Exit(2)
			}
		}
		code := 0
		if !d.Clean() {
			code = 1
		}
		out(map[string]any{"drift": d, "repaired": repaired}, code)
	default:
		fmt.Fprintln(os.Stderr, "pfbackupdrill: --command is required (pitr|full|tenant|reconcile|region)")
		os.Exit(2)
	}
}

func timeSeconds(s float64) time.Duration { return time.Duration(s * float64(time.Second)) }
