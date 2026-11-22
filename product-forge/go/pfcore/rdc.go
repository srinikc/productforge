// rdc.go — Runtime Dependency Compiler (A5, BI-PF-0399)
// Authoritative runtime composition engine + fail-closed IP-leakage guard in native Go.
// Composes EAP manifest + target OS/arch + license profile into a deterministic runtime package plan.
// Refuses any composition for customer-delivered editions (enterprise, saas, on-prem, oem) that exposes raw .py sources.
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// Supported OS and architecture targets for v1
var supportedTargets = map[string][]string{
	"linux":   {"amd64", "arm64"},
	"windows": {"amd64"},
	"darwin":  {"arm64", "amd64"},
}

// Customer editions subject to strict zero-raw-.py enforcement
var customerEditions = map[string]bool{
	"enterprise": true,
	"on-prem":    true,
	"saas":       true,
	"oem":        true,
}

// RDCCompositionSchema is the canonical contract schema constant
const RDCCompositionSchema = "product-forge/runtime-composition@1"

// IsCustomerEdition returns true if the edition is commercial/customer delivered
func IsCustomerEdition(edition string) bool {
	return customerEditions[strings.ToLower(strings.TrimSpace(edition))]
}

// ValidateTarget checks if the OS and architecture pair is supported
func ValidateTarget(osName, arch string) bool {
	osLower := strings.ToLower(strings.TrimSpace(osName))
	archLower := strings.ToLower(strings.TrimSpace(arch))
	archs, ok := supportedTargets[osLower]
	if !ok {
		return false
	}
	for _, a := range archs {
		if a == archLower {
			return true
		}
	}
	return false
}

// ValidateIPLeakage inspects files/components for raw .py sources in customer editions (fail-closed)
func ValidateIPLeakage(req WireRequest) WireResponse {
	payload := req.Payload
	if payload == nil {
		return response(req, false, "error", nil, "payload must be an object")
	}

	edition, _ := payload["edition"].(string)
	edition = strings.ToLower(strings.TrimSpace(edition))
	if edition == "" {
		edition = "community"
	}

	var files []string
	if rawFiles, ok := payload["files"].([]any); ok {
		for _, f := range rawFiles {
			if s, isStr := f.(string); isStr {
				files = append(files, s)
			}
		}
	} else if rawComponents, ok := payload["components"].([]any); ok {
		for _, c := range rawComponents {
			if m, isMap := c.(map[string]any); isMap {
				if p, hasPath := m["path"].(string); hasPath {
					files = append(files, p)
				}
				if b, hasBin := m["binary"].(string); hasBin {
					files = append(files, b)
				}
			}
		}
	}

	isCustomer := IsCustomerEdition(edition)
	unmet := []string{}
	var leakingFiles []string

	for _, file := range files {
		clean := filepath.ToSlash(strings.TrimSpace(file))
		lower := strings.ToLower(clean)
		if strings.HasSuffix(lower, ".py") && !strings.HasSuffix(lower, ".pyc") && !strings.HasSuffix(lower, ".pyd") {
			if isCustomer {
				unmet = append(unmet, "ip_leakage:raw_py:"+clean)
				leakingFiles = append(leakingFiles, clean)
			}
		}
	}

	valid := len(unmet) == 0
	errMsg := ""
	status := "ok"
	if !valid {
		status = "error"
		errMsg = fmt.Sprintf("IP_LEAKAGE_DETECTED: raw .py source files forbidden in customer edition %q: %s",
			edition, strings.Join(leakingFiles, ", "))
	}

	return response(req, valid, status, map[string]any{
		"valid":         valid,
		"edition":       edition,
		"is_customer":   isCustomer,
		"checked_files": len(files),
		"unmet":         unmet,
		"leaking_files": leakingFiles,
		"ip_zone":       "A",
		"evaluated_at":  time.Now().UTC().Format(time.RFC3339),
	}, errMsg)
}

// Compose executes deterministic runtime composition from EAP, target OS/arch, and license
func Compose(req WireRequest) WireResponse {
	payload := req.Payload
	if payload == nil {
		return response(req, false, "error", nil, "payload must be an object")
	}

	eap, _ := payload["eap"].(map[string]any)
	edition, _ := payload["edition"].(string)
	if edition == "" && eap != nil {
		edition, _ = eap["edition"].(string)
	}
	edition = strings.ToLower(strings.TrimSpace(edition))
	if edition == "" {
		edition = "community"
	}

	targetOS, _ := payload["target_os"].(string)
	if targetOS == "" {
		targetOS = "linux"
	}
	targetOS = strings.ToLower(strings.TrimSpace(targetOS))

	targetArch, _ := payload["target_arch"].(string)
	if targetArch == "" {
		targetArch = "amd64"
	}
	targetArch = strings.ToLower(strings.TrimSpace(targetArch))

	if !ValidateTarget(targetOS, targetArch) {
		return response(req, false, "error", nil,
			fmt.Sprintf("ERR_RDC_UNSUPPORTED_TARGET: %s/%s is not a supported target", targetOS, targetArch))
	}

	licenseTier, _ := payload["license_tier"].(string)
	if licenseTier == "" && eap != nil {
		licenseTier, _ = eap["tier"].(string)
	}

	dryRun, _ := payload["dry_run"].(bool)

	// Determine binary and library extensions per target OS
	binExt := ""
	libExt := ".so"
	if targetOS == "windows" {
		binExt = ".exe"
		libExt = ".pyd"
	} else if targetOS == "darwin" {
		libExt = ".dylib"
	}

	// Default components composed based on edition and target
	binName := "pf-core" + binExt
	coreRuntimeLib := "core_runtime" + libExt
	apiRuntimeLib := "api_runtime" + libExt

	components := []map[string]any{
		{
			"component_id":       "pf-core-native",
			"name":               "pf-core",
			"language":           "go",
			"type":               "binary",
			"binary":             binName,
			"path":               "bin/" + binName,
			"compiled":           true,
			"runtime_required":   true,
			"customer_delivered": true,
			"ip_zone":            "A",
			"version":            "1.0.0",
		},
		{
			"component_id":       "pf-core-runtime",
			"name":               "core_runtime",
			"language":           "python",
			"type":               "shared_library",
			"binary":             coreRuntimeLib,
			"path":               "lib/" + coreRuntimeLib,
			"compiled":           true,
			"runtime_required":   true,
			"customer_delivered": true,
			"ip_zone":            "A",
			"version":            "1.0.0",
		},
		{
			"component_id":       "pf-api-runtime",
			"name":               "api_runtime",
			"language":           "python",
			"type":               "shared_library",
			"binary":             apiRuntimeLib,
			"path":               "lib/" + apiRuntimeLib,
			"compiled":           true,
			"runtime_required":   true,
			"customer_delivered": true,
			"ip_zone":            "A",
			"version":            "1.0.0",
		},
	}

	// Handle custom or additional component definitions from EAP if present
	if eap != nil {
		if rawComps, ok := eap["components"].([]any); ok {
			for _, rc := range rawComps {
				if cm, ok := rc.(map[string]any); ok {
					cid, _ := cm["component_id"].(string)
					if cid != "" && cid != "pf-core-native" {
						components = append(components, cm)
					}
				}
			}
		}
	}

	// Sort components deterministically by component_id
	sort.Slice(components, func(i, j int) bool {
		return fmt.Sprintf("%v", components[i]["component_id"]) < fmt.Sprintf("%v", components[j]["component_id"])
	})

	// Collect file paths for IP-leakage check
	var filesToCheck []string
	checksums := map[string]string{}
	for _, c := range components {
		if p, ok := c["path"].(string); ok {
			p = filepath.ToSlash(p)
			filesToCheck = append(filesToCheck, p)
			h := sha256.Sum256([]byte(p + ":" + targetOS + ":" + targetArch))
			checksums[p] = hex.EncodeToString(h[:])
		}
	}

	// Fail-closed IP-leakage guard check
	ipReq := WireRequest{
		Schema:       WireRequestSchema,
		ID:           req.ID + "-ip",
		Op:           "rdc.validate_ip",
		ContractName: "rdc-ip-guard",
		Payload: map[string]any{
			"edition": edition,
			"files":   filesToCheck,
		},
	}
	ipResp := ValidateIPLeakage(ipReq)
	if !ipResp.OK {
		return response(req, false, "error", ipResp.Result, ipResp.Error)
	}

	composition := map[string]any{
		"schema":            RDCCompositionSchema,
		"edition":           edition,
		"tier":              licenseTier,
		"target_os":         targetOS,
		"target_arch":       targetArch,
		"target_platform":   targetOS + "/" + targetArch,
		"dry_run":           dryRun,
		"components":        components,
		"native_binaries":   []string{binName},
		"shared_libraries":  []string{coreRuntimeLib, apiRuntimeLib},
		"checksums":         checksums,
		"ip_zone":           "A",
		"ip_guard_verified": true,
		"generated_at":      time.Now().UTC().Format(time.RFC3339),
	}

	return response(req, true, "ok", composition, "")
}

// Plan outputs the planned directory layout and file list for package assembly
func Plan(req WireRequest) WireResponse {
	compResp := Compose(req)
	if !compResp.OK {
		return compResp
	}
	comp := compResp.Result
	var paths []string
	if comps, ok := comp["components"].([]map[string]any); ok {
		for _, c := range comps {
			if p, ok := c["path"].(string); ok {
				paths = append(paths, filepath.ToSlash(p))
			}
		}
	}
	sort.Strings(paths)
	return response(req, true, "ok", map[string]any{
		"plan_schema":  "product-forge/runtime-package-plan@1",
		"edition":      comp["edition"],
		"target":       comp["target_platform"],
		"paths":        paths,
		"total_files":  len(paths),
		"composition":  comp,
		"generated_at": time.Now().UTC().Format(time.RFC3339),
	}, "")
}
