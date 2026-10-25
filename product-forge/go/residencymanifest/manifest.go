package residencymanifest

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

const SchemaVersion = "1.0"

var homeRE = regexp.MustCompile(`^[a-zA-Z0-9-]+$`)

var Frequencies = map[string]bool{"hourly": true, "daily": true, "weekly": true, "monthly": true}

type Backup struct {
	Regions   []string `json:"regions"`
	Encrypted bool     `json:"encrypted"`
	Frequency string   `json:"frequency"`
}
type KMS struct {
	Provider     string `json:"provider"`
	Region       string `json:"region"`
	RotationDays int    `json:"rotation_days"`
}
type Egress struct {
	AllowedRegions []string `json:"allowed_regions"`
	Subprocessors  []string `json:"subprocessors"`
}
type Retention struct {
	Days      int  `json:"days"`
	LegalHold bool `json:"legal_hold"`
}
type Manifest struct {
	SchemaVersion  string    `json:"schema_version"`
	Template       bool      `json:"template"`
	DataClasses    []string  `json:"data_classes"`
	HomeRegion     string    `json:"home_region"`
	AllowedRegions []string  `json:"allowed_regions"`
	Backup         Backup    `json:"backup"`
	KMS            KMS       `json:"kms"`
	Egress         *Egress   `json:"egress"`
	Retention      Retention `json:"retention"`
}
type Profile struct {
	ID             string   `json:"id"`
	Region         string   `json:"region"`
	AllowedRegions []string `json:"allowed_regions"`
	RetentionDays  int      `json:"retention_days"`
}

func LoadManifest(path string) (Manifest, error) {
	var m Manifest
	if st, err := os.Stat(path); err != nil {
		return m, fmt.Errorf("RESIDENCY_MANIFEST_UNREADABLE: %w", err)
	} else if st.Size() > 64*1024 {
		return m, errors.New("RESIDENCY_MANIFEST_TOO_LARGE")
	}
	b, err := os.ReadFile(path)
	if err != nil {
		return m, fmt.Errorf("RESIDENCY_MANIFEST_UNREADABLE: %w", err)
	}
	b = bytes.TrimPrefix(b, []byte{0xEF, 0xBB, 0xBF})
	if err := json.Unmarshal(b, &m); err != nil {
		return m, fmt.Errorf("RESIDENCY_MANIFEST_INVALID: %w", err)
	}
	return m, nil
}

func LoadProfile(dir, home string) (Profile, error) {
	var p Profile
	if strings.TrimSpace(home) == "" || !homeRE.MatchString(home) {
		return p, errors.New("RESIDENCY_UNKNOWN_HOME")
	}
	path := filepath.Join(dir, strings.ToLower(home)+"-v1.json")
	if st, err := os.Stat(path); err != nil {
		return p, fmt.Errorf("RESIDENCY_PROFILE_UNREADABLE: %w", err)
	} else if st.Size() > 64*1024 {
		return p, errors.New("RESIDENCY_PROFILE_TOO_LARGE")
	}
	b, err := os.ReadFile(path)
	if err != nil {
		return p, fmt.Errorf("RESIDENCY_PROFILE_UNREADABLE: %w", err)
	}
	b = bytes.TrimPrefix(b, []byte{0xEF, 0xBB, 0xBF})
	if err := json.Unmarshal(b, &p); err != nil {
		return p, fmt.Errorf("RESIDENCY_PROFILE_UNREADABLE: %w", err)
	}
	return p, nil
}

func upperSet(xs []string) map[string]bool {
	out := map[string]bool{}
	for _, x := range xs {
		out[strings.ToUpper(strings.TrimSpace(x))] = true
	}
	return out
}

func subset(xs []string, allowed map[string]bool) bool {
	for _, x := range xs {
		if !allowed[strings.ToUpper(strings.TrimSpace(x))] {
			return false
		}
	}
	return true
}

// Validate returns stable error codes; an empty slice means pass.
func Validate(m Manifest, p Profile) []string {
	var errs []string
	add := func(c string) { errs = append(errs, c) }
	if m.SchemaVersion != SchemaVersion {
		add("RESIDENCY_SCHEMA_VERSION")
	}
	if len(m.DataClasses) == 0 {
		add("RESIDENCY_MISSING_GROUP:data_classes")
	}
	if strings.TrimSpace(m.HomeRegion) == "" {
		add("RESIDENCY_MISSING_GROUP:home_region")
	}
	if len(m.AllowedRegions) == 0 {
		add("RESIDENCY_MISSING_GROUP:allowed_regions")
	}
	if len(m.Backup.Regions) == 0 && !m.Backup.Encrypted && m.Backup.Frequency == "" {
		add("RESIDENCY_MISSING_GROUP:backup")
	}
	if m.KMS.Provider == "" && m.KMS.Region == "" && m.KMS.RotationDays == 0 {
		add("RESIDENCY_MISSING_GROUP:kms")
	}
	if m.Retention.Days == 0 && !m.Retention.LegalHold {
		add("RESIDENCY_MISSING_GROUP:retention")
	}
	home := strings.ToUpper(strings.TrimSpace(m.HomeRegion))
	if home == "" {
		add("RESIDENCY_UNKNOWN_HOME")
	}
	allowed := upperSet(p.AllowedRegions)
	if p.ID == "" || len(allowed) == 0 {
		add("RESIDENCY_PROFILE_UNREADABLE")
	}
	if home != "" && !allowed[home] {
		add("RESIDENCY_HOME_NOT_ALLOWED")
	}
	if len(m.AllowedRegions) == 0 || !upperSet(m.AllowedRegions)[home] {
		add("RESIDENCY_HOME_NOT_ALLOWED")
	} else if !subset(m.AllowedRegions, allowed) {
		add("RESIDENCY_REGION_NOT_ALLOWED")
	}
	if !subset(m.Backup.Regions, allowed) {
		add("RESIDENCY_BACKUP_REGION")
	}
	if m.KMS.Region != "" && !allowed[strings.ToUpper(strings.TrimSpace(m.KMS.Region))] {
		add("RESIDENCY_KMS_REGION")
	}
	if m.Egress == nil {
		add("RESIDENCY_MISSING_GROUP:egress")
	} else if !subset(m.Egress.AllowedRegions, allowed) {
		add("RESIDENCY_EGRESS_REGION")
	}
	if !m.Backup.Encrypted {
		add("RESIDENCY_BACKUP_UNENCRYPTED")
	}
	if !Frequencies[strings.ToLower(m.Backup.Frequency)] {
		add("RESIDENCY_UNKNOWN_FREQUENCY")
	}
	if m.KMS.Provider == "" {
		add("RESIDENCY_INVALID_FIELD:kms.provider")
	}
	if m.KMS.RotationDays <= 0 {
		add("RESIDENCY_KMS_ROTATION")
	}
	if m.Retention.Days <= 0 || (p.RetentionDays > 0 && !m.Retention.LegalHold && m.Retention.Days > p.RetentionDays) {
		add("RESIDENCY_RETENTION")
	}
	return errs
}
