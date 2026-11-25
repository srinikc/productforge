// Command pfingest ingests file-backed intake-raw/builds stores into the EDP object store + artifact
// metadata (BI-PF-1475). It is an operator tool; the tenant is supplied explicitly and the DSN/object root
// come from the environment so credentials never appear in argv.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"productforge/intakeingest"
	"productforge/objstore"
	"productforge/store"
)

func logResult(r intakeingest.FileResult, runID string) {
	line := struct {
		Level  string                  `json:"level"`
		RunID  string                  `json:"run_id"`
		Result intakeingest.FileResult `json:"result"`
	}{Level: "INFO", RunID: runID, Result: r}
	b, err := json.Marshal(line)
	if err != nil {
		fmt.Fprintf(os.Stderr, "{\"level\":\"ERROR\",\"msg\":\"cannot encode log line: %s\"}\n", err)
		return
	}
	fmt.Fprintln(os.Stderr, string(b))
}

func collect(root, name string) ([]string, error) {
	if strings.TrimSpace(root) == "" {
		return nil, fmt.Errorf("intakeingest: --root (source directory) is required")
	}
	abs, err := filepath.Abs(root)
	if err != nil {
		return nil, err
	}
	if name != "" {
		rel := filepath.Clean(name)
		if filepath.IsAbs(rel) || rel == ".." || strings.HasPrefix(rel, ".."+string(os.PathSeparator)) {
			return nil, fmt.Errorf("intakeingest: --name must stay under --root")
		}
		if strings.EqualFold(filepath.Base(rel), "product_forge_context.json") {
			return nil, fmt.Errorf("intakeingest: legacy dashboard store is out of scope (stays planned under BI-PF-1292)")
		}
		return []string{filepath.ToSlash(rel)}, nil
	}
	var out []string
	err = filepath.WalkDir(abs, func(p string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		rel, err := filepath.Rel(abs, p)
		if err != nil {
			return err
		}
		slash := filepath.ToSlash(rel)
		if strings.EqualFold(filepath.Base(slash), "product_forge_context.json") {
			fmt.Fprintf(os.Stderr, "pfingest: skipping legacy store %s (out of scope)\n", slash)
			return nil
		}
		out = append(out, slash)
		return nil
	})
	if err != nil {
		return nil, err
	}
	return out, nil
}

func preflightWritable(path string) error {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	return f.Close()
}

func run() int {
	var tenant, bucket, root, name, contentType, reportFile, objectRoot string
	var maxBytes int64
	var dryRun, verify, orphans, allowBypass bool
	flag.StringVar(&tenant, "tenant", "", "tenant id that owns the ingested artifacts (required)")
	flag.StringVar(&bucket, "bucket", "", "store bucket: intake or builds")
	flag.StringVar(&root, "root", "", "source directory")
	flag.StringVar(&name, "name", "", "single file relative to --root (default: all files)")
	flag.StringVar(&contentType, "content-type", "application/octet-stream", "content type for a single-file ingest")
	flag.Int64Var(&maxBytes, "max-bytes", intakeingest.DefaultMaxBytes, "per-file size cap in bytes")
	flag.BoolVar(&dryRun, "dry-run", false, "hash and report planned writes without mutating")
	flag.BoolVar(&verify, "verify", false, "verify the source against stored metadata and objects")
	flag.BoolVar(&orphans, "orphans", false, "with --verify, list unreferenced objects under the tenant prefix")
	flag.StringVar(&reportFile, "report-file", "", "write the pf.intake-ingest/1 report to this path")
	flag.BoolVar(&allowBypass, "allow-bypassrls", false, "allow a BYPASSRLS role (local test DB only)")
	flag.Parse()
	runStart := time.Now()

	fail := func(format string, args ...any) int {
		fmt.Fprintf(os.Stderr, "pfingest: "+format+"\n", args...)
		return 2
	}

	dsn := os.Getenv("PF_RUNTIME_DSN")
	if dsn == "" {
		return fail("PF_RUNTIME_DSN is required (non-BYPASSRLS runtime role)")
	}
	if tenant == "" {
		return fail("--tenant is required")
	}
	if bucket != intakeingest.BucketIntake && bucket != intakeingest.BucketBuilds {
		return fail("--bucket must be %q or %q", intakeingest.BucketIntake, intakeingest.BucketBuilds)
	}
	if reportFile != "" {
		if err := preflightWritable(reportFile); err != nil {
			return fail("--report-file is not writable: %v", err)
		}
	}
	if verify && dryRun {
		return fail("--dry-run is only valid with ingest (not --verify)")
	}
	if allowBypass && (os.Getenv("PF_CI") != "" || os.Getenv("PF_ALLOW_BYPASSRLS") != "1") {
		return fail("--allow-bypassrls is denied: set PF_ALLOW_BYPASSRLS=1 and unset PF_CI (local test DB only)")
	}

	objectRoot = os.Getenv("PF_OBJECT_ROOT")
	if objectRoot == "" {
		return fail("PF_OBJECT_ROOT is required (local object store root)")
	}

	ctx := context.Background()
	st, err := store.Open(ctx, dsn)
	if err != nil {
		return fail("cannot open the database: %v", err)
	}
	defer st.Close()

	posture, err := intakeingest.EnsureRuntimeRole(ctx, st, allowBypass)
	if err != nil {
		return fail("%v", err)
	}
	if posture.BypassRLS || posture.Superuser {
		fmt.Fprintf(os.Stderr,
			`{"level":"HIGH","msg":"bypassrls role accepted","role":%q,"superuser":%v,"bypassrls":%v}`+"\n",
			posture.Name, posture.Superuser, posture.BypassRLS)
	}

	obj, err := objstore.NewLocalStore(objectRoot, 0)
	if err != nil {
		return fail("cannot open the object store: %v", err)
	}
	svc := intakeingest.New(store.BindTenant(st, tenant), obj, maxBytes)
	files, err := collect(root, name)
	if err != nil {
		return fail("%v", err)
	}
	if len(files) == 0 {
		return fail("no source files under %s", root)
	}

	mode := "ingest"
	if verify {
		mode = "verify"
	}
	runID, err := intakeingest.NewRunID()
	if err != nil {
		return fail("%v", err)
	}
	report := intakeingest.NewReport(runID, mode, tenant, dryRun)
	report.StartedAt = runStart.UTC()
	for _, rel := range files {
		f, err := os.Open(filepath.Join(root, filepath.FromSlash(rel)))
		if err != nil {
			r := intakeingest.FileResult{Store: bucket + "/" + rel, Bucket: bucket, Name: rel,
				Status: intakeingest.Failed, Error: err.Error()}
			report.Add(r)
			logResult(r, runID)
			continue
		}
		var res intakeingest.FileResult
		if verify {
			res, err = svc.Verify(ctx, tenant, bucket, rel, f)
		} else {
			res, err = svc.Ingest(ctx, tenant, bucket, rel, f, contentType, dryRun)
		}
		_ = f.Close()
		if err != nil && res.Status == "" {
			res.Status = intakeingest.Failed
			res.Error = err.Error()
		}
		report.Add(res)
		logResult(res, runID)
	}
	if verify && orphans {
		list, err := svc.Orphans(ctx, tenant, bucket)
		if err != nil {
			return fail("orphan scan failed: %v", err)
		}
		report.OrphanObjects = list
	}
	report.DurationMS = time.Since(runStart).Milliseconds()

	out, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return fail("cannot encode the report: %v", err)
	}
	fmt.Println(string(out))
	if reportFile != "" {
		if err := os.WriteFile(reportFile, append(out, '\n'), 0o644); err != nil {
			return fail("cannot write --report-file: %v", err)
		}
	}
	return intakeingest.ExitCode(report)
}

func main() { os.Exit(run()) }
