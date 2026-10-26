package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strings"

	"productforge/residencymanifest"
)

func main() {
	manifestPath := flag.String("manifest", "", "residency manifest path")
	profileDir := flag.String("profiles", "config/residency-profiles", "profile directory")
	mode := flag.String("mode", "block", "block|warn")
	report := flag.Bool("report", false, "write JSON report to stdout")
	flag.Parse()
	if *manifestPath == "" {
		fmt.Fprintln(os.Stderr, "RESIDENCY_MANIFEST_UNREADABLE: --manifest is required")
		os.Exit(2)
	}
	m, err := residencymanifest.LoadManifest(*manifestPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	p, err := residencymanifest.LoadProfile(*profileDir, m.HomeRegion)
	if err != nil {
		code := "RESIDENCY_PROFILE_UNREADABLE"
		if strings.Contains(err.Error(), "RESIDENCY_UNKNOWN_HOME") {
			code = "RESIDENCY_UNKNOWN_HOME"
		}
		b, _ := json.Marshal(map[string]any{"ok": false, "mode": *mode, "home_region": m.HomeRegion,
			"report_version": 1, "errors": []string{code}})
		fmt.Println(string(b))
		os.Exit(1)
	}
	errs := residencymanifest.Validate(m, p)
	out := map[string]any{"ok": len(errs) == 0, "mode": *mode, "home_region": m.HomeRegion,
		"profile": p.ID, "report_version": 1, "errors": errs}
	if *report || len(errs) > 0 {
		b, _ := json.Marshal(out)
		fmt.Println(string(b))
	}
	if len(errs) == 0 {
		return
	}
	if *mode == "warn" {
		hard := false
		for _, e := range errs {
			for _, p := range []string{"RESIDENCY_UNKNOWN_HOME", "RESIDENCY_PROFILE_UNREADABLE", "RESIDENCY_SCHEMA_VERSION",
				"RESIDENCY_MISSING_GROUP", "RESIDENCY_INVALID_FIELD", "RESIDENCY_BACKUP_UNENCRYPTED", "RESIDENCY_KMS_ROTATION",
				"RESIDENCY_UNKNOWN_FREQUENCY", "RESIDENCY_HOME_NOT_ALLOWED", "RESIDENCY_REGION_NOT_ALLOWED",
				"RESIDENCY_BACKUP_REGION", "RESIDENCY_KMS_REGION", "RESIDENCY_EGRESS_REGION", "RESIDENCY_RETENTION"} {
				if strings.HasPrefix(e, p) {
					hard = true
				}
			}
		}
		if !hard {
			fmt.Fprintf(os.Stderr, "residency: WARN %d violation(s): %v\n", len(errs), errs)
			os.Exit(0)
		}
	}
	os.Exit(1)
}
