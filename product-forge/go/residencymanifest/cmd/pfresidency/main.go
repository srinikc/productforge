package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

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
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
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
		fmt.Fprintf(os.Stderr, "residency: WARN %d violation(s): %v\n", len(errs), errs)
		os.Exit(0)
	}
	os.Exit(1)
}
