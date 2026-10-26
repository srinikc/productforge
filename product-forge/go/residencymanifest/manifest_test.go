package residencymanifest

import "testing"

func base() (Manifest, Profile) {
	m := Manifest{SchemaVersion: "1.0", DataClasses: []string{"product_metadata"}, HomeRegion: "IN",
		AllowedRegions: []string{"IN"}, Backup: Backup{Regions: []string{"IN"}, Encrypted: true, Frequency: "daily"},
		KMS: KMS{Provider: "local", Region: "IN", RotationDays: 90}, Egress: &Egress{}, Retention: Retention{Days: 365}}
	p := Profile{ID: "in-v1", Region: "IN", AllowedRegions: []string{"IN"}, RetentionDays: 730}
	return m, p
}

func has(errs []string, code string) bool {
	for _, e := range errs {
		if e == code {
			return true
		}
	}
	return false
}

func TestValid(t *testing.T) {
	m, p := base()
	if errs := Validate(m, p); len(errs) != 0 {
		t.Fatalf("want pass, got %v", errs)
	}
}

func TestUnknownHome(t *testing.T) {
	m, p := base()
	m.HomeRegion = "XX"
	if errs := Validate(m, p); !has(errs, "RESIDENCY_HOME_NOT_ALLOWED") {
		t.Fatalf("want HOME_NOT_ALLOWED, got %v", errs)
	}
}

func TestMissingHome(t *testing.T) {
	m, p := base()
	m.HomeRegion = ""
	if errs := Validate(m, p); !has(errs, "RESIDENCY_UNKNOWN_HOME") {
		t.Fatalf("want UNKNOWN_HOME, got %v", errs)
	}
}

func TestRegionWideningRejected(t *testing.T) {
	m, p := base()
	m.AllowedRegions = []string{"IN", "US"}
	if errs := Validate(m, p); !has(errs, "RESIDENCY_REGION_NOT_ALLOWED") {
		t.Fatalf("want REGION_NOT_ALLOWED, got %v", errs)
	}
}

func TestBackupAndKMS(t *testing.T) {
	m, p := base()
	m.Backup.Regions = []string{"US"}
	m.KMS.Region = "US"
	m.Egress = &Egress{AllowedRegions: []string{"US"}}
	m.Backup.Encrypted = false
	m.Backup.Frequency = "sometimes"
	m.KMS.RotationDays = 0
	errs := Validate(m, p)
	for _, c := range []string{"RESIDENCY_BACKUP_REGION", "RESIDENCY_KMS_REGION", "RESIDENCY_EGRESS_REGION",
		"RESIDENCY_BACKUP_UNENCRYPTED", "RESIDENCY_UNKNOWN_FREQUENCY", "RESIDENCY_KMS_ROTATION"} {
		if !has(errs, c) {
			t.Fatalf("missing %s in %v", c, errs)
		}
	}
}

func TestRetention(t *testing.T) {
	m, p := base()
	m.Retention.Days = 0
	if errs := Validate(m, p); !has(errs, "RESIDENCY_RETENTION") {
		t.Fatalf("want RETENTION, got %v", errs)
	}
	m.Retention.Days = 731
	if errs := Validate(m, p); !has(errs, "RESIDENCY_RETENTION") {
		t.Fatalf("want over-policy RETENTION, got %v", errs)
	}
	m.Retention.LegalHold = true
	if errs := Validate(m, p); has(errs, "RESIDENCY_RETENTION") {
		t.Fatalf("legal hold should exempt max, got %v", errs)
	}
}

func TestSchemaVersion(t *testing.T) {
	m, p := base()
	m.SchemaVersion = "2.0"
	if errs := Validate(m, p); !has(errs, "RESIDENCY_SCHEMA_VERSION") {
		t.Fatalf("want SCHEMA_VERSION, got %v", errs)
	}
}

func TestPathTraversalRejected(t *testing.T) {
	_, err := LoadProfile("config/residency-profiles", "../in")
	if err == nil {
		t.Fatal("want traversal rejected")
	}
}

func TestMissingGroups(t *testing.T) {
	m, p := base()
	m.DataClasses = nil
	m.HomeRegion = ""
	m.AllowedRegions = nil
	m.Backup = Backup{}
	m.KMS = KMS{}
	m.Retention = Retention{}
	errs := Validate(m, p)
	for _, c := range []string{"RESIDENCY_MISSING_GROUP:data_classes", "RESIDENCY_MISSING_GROUP:home_region",
		"RESIDENCY_MISSING_GROUP:allowed_regions", "RESIDENCY_MISSING_GROUP:backup",
		"RESIDENCY_MISSING_GROUP:kms", "RESIDENCY_MISSING_GROUP:retention"} {
		if !has(errs, c) {
			t.Fatalf("missing %s in %v", c, errs)
		}
	}
}

func TestKMSProvider(t *testing.T) {
	m, p := base()
	m.KMS.Provider = ""
	if errs := Validate(m, p); !has(errs, "RESIDENCY_INVALID_FIELD:kms.provider") {
		t.Fatalf("want provider field error, got %v", errs)
	}
}
