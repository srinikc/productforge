package limits

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func env(m map[string]string) Getenv {
	return func(k string) string { return m[k] }
}

func TestLoadDefaults(t *testing.T) {
	c, err := Load(env(nil))
	if err != nil {
		t.Fatal(err)
	}
	if c.Profile != ProfileDev || !c.Enforce || c.RequestTimeout != 30*time.Second ||
		c.DBTimeout != 5*time.Second || c.UploadTimeout != 120*time.Second || c.MigrationTimeout != 150*time.Second ||
		c.MaxBodyBytes != 1<<20 || c.MaxUploadBytes != 64<<20 ||
		c.Pool.MaxConns != 10 || c.GlobalConcurrency != 10 || c.TenantRPM != 600 {
		t.Fatalf("unexpected defaults: %+v", c)
	}
}

func TestLoadEnvOverrides(t *testing.T) {
	c, err := Load(env(map[string]string{
		"PF_PROFILE": "production", "PF_EDP_ENFORCE_LIMITS": "1",
		"PF_EDP_REQUEST_TIMEOUT": "12s", "PF_EDP_DB_TIMEOUT": "2s", "PF_EDP_UPLOAD_TIMEOUT": "60s",
		"PF_EDP_READ_TIMEOUT": "120s", "PF_EDP_WRITE_TIMEOUT": "120s", "PF_EDP_MIGRATION_TIMEOUT": "60s",
		"PF_EDP_MAX_BODY_BYTES": "2048", "PF_EDP_MAX_UPLOAD_BYTES": "4096",
		"PF_EDP_GLOBAL_CONCURRENCY": "4", "PF_EDP_POOL_MAX_CONNS": "4",
		"PF_EDP_TENANT_RPM": "30", "PF_EDP_GLOBAL_RPM": "120", "PF_EDP_TENANT_CONCURRENCY": "2",
	}))
	if err != nil {
		t.Fatal(err)
	}
	if c.RequestTimeout != 12*time.Second || c.MaxBodyBytes != 2048 || c.GlobalConcurrency != 4 ||
		c.Pool.MaxConns != 4 || c.TenantRPM != 30 {
		t.Fatalf("overrides not applied: %+v", c)
	}
}

func TestValidateRejectsUnsafeCombinations(t *testing.T) {
	cases := []struct {
		name string
		mut  func(*Config)
		want string
	}{
		{"global concurrency > pool", func(c *Config) { c.GlobalConcurrency = 11 }, "GLOBAL_CONCURRENCY"},
		{"db > request", func(c *Config) { c.DBTimeout = 60 * time.Second }, "DB_TIMEOUT"},
		{"upload < request", func(c *Config) { c.UploadTimeout = time.Second }, "UPLOAD_TIMEOUT"},
		{"request > read", func(c *Config) { c.ReadTimeout = 5 * time.Second }, "read/write"},
		{"upload > write", func(c *Config) { c.WriteTimeout = 60 * time.Second }, "read/write"},
		{"bad profile", func(c *Config) { c.Profile = "staging" }, "PF_PROFILE"},
		{"prod kill switch", func(c *Config) { c.Profile = ProfileProduction; c.Enforce = false }, "ENFORCE_LIMITS"},
		{"prod superuser", func(c *Config) { c.Profile = ProfileProduction; c.AllowSuperuserDSN = true }, "SUPERUSER"},
		{"body > upload", func(c *Config) { c.MaxBodyBytes = c.MaxUploadBytes + 1 }, "upload"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			c := DefaultConfig()
			tc.mut(&c)
			err := c.Validate()
			if err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("want error containing %q, got %v", tc.want, err)
			}
		})
	}
}

func TestValidateProfileProduction(t *testing.T) {
	c := DefaultConfig()
	c.Profile = ProfileProduction
	if err := ValidateProfile(c, env(map[string]string{"PF_ADMIN_TOKEN": strings.Repeat("a", 32)})); err != nil {
		t.Fatalf("strong token must pass: %v", err)
	}
	for name, m := range map[string]map[string]string{
		"dev flag":   {"PF_ADMIN_TOKEN": strings.Repeat("a", 32), "PF_DEV": "1"},
		"anon flag":  {"PF_ADMIN_TOKEN": strings.Repeat("a", 32), "API_ALLOW_ANON": "1"},
		"anon alias": {"PF_ADMIN_TOKEN": strings.Repeat("a", 32), "PF_ALLOW_ANON": "true"},
		"missing":    {},
		"short":      {"PF_ADMIN_TOKEN": "short"},
		"weak":       {"PF_ADMIN_TOKEN": "changeme"},
	} {
		if err := ValidateProfile(c, env(m)); err == nil {
			t.Fatalf("%s: production must reject", name)
		}
	}
	// Dev profile tolerates anon/dev flags.
	dev := DefaultConfig()
	if err := ValidateProfile(dev, env(map[string]string{"PF_DEV": "1", "API_ALLOW_ANON": "1"})); err != nil {
		t.Fatalf("dev profile must accept anon: %v", err)
	}
}

func TestStrictBooleanAndGlobalRPM(t *testing.T) {
	if _, err := Load(env(map[string]string{"PF_EDP_ENFORCE_LIMITS": "maybe"})); err == nil {
		t.Fatal("an unknown enforcement flag must fail closed")
	}
	if _, err := Load(env(map[string]string{"PF_EDP_GLOBAL_RPM": "100", "PF_EDP_TENANT_RPM": "600"})); err == nil {
		t.Fatal("global RPM below tenant RPM must be rejected")
	}
	c := DefaultConfig()
	c.Profile = ProfileProduction
	if err := ValidateProfile(c, env(map[string]string{"PF_ADMIN_TOKEN": strings.Repeat("a", 32),
		"API_ALLOW_ANON": "maybe"})); err == nil {
		t.Fatalf("an unknown dev-auth flag value must fail closed in production")
	}
}

func TestEnvFlagDefaultsMatch(t *testing.T) {
	path := filepath.Join("..", "..", "..", "..", "config", "env-flags.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Skip("config/env-flags.json not available from the test working directory")
	}
	var doc struct {
		Flags map[string]struct {
			Default string `json:"default"`
		} `json:"flags"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatal(err)
	}
	c := DefaultConfig()
	want := map[string]string{
		"PF_PROFILE": c.Profile, "PF_EDP_ENFORCE_LIMITS": "1",
		"PF_EDP_REQUEST_TIMEOUT": c.RequestTimeout.String(), "PF_EDP_DB_TIMEOUT": c.DBTimeout.String(),
		"PF_EDP_UPLOAD_TIMEOUT": c.UploadTimeout.String(), "PF_EDP_MIGRATION_TIMEOUT": c.MigrationTimeout.String(),
		"PF_EDP_READ_HEADER_TIMEOUT": c.ReadHeaderTimeout.String(), "PF_EDP_READ_TIMEOUT": c.ReadTimeout.String(),
		"PF_EDP_WRITE_TIMEOUT": c.WriteTimeout.String(), "PF_EDP_IDLE_TIMEOUT": c.IdleTimeout.String(),
		"PF_EDP_MAX_HEADER_BYTES": "1048576", "PF_EDP_MAX_BODY_BYTES": "1048576",
		"PF_EDP_MAX_UPLOAD_BYTES": "67108864", "PF_EDP_POOL_MAX_CONNS": "10", "PF_EDP_POOL_MIN_CONNS": "1",
		"PF_EDP_POOL_CONNECT_TIMEOUT": "10s", "PF_EDP_POOL_CONN_LIFETIME": "1h0m0s",
		"PF_EDP_POOL_CONN_IDLE": "30m0s", "PF_EDP_POOL_HEALTH_PERIOD": "1m0s",
		"PF_EDP_TENANT_RPM": "600", "PF_EDP_GLOBAL_RPM": "6000", "PF_EDP_TENANT_CONCURRENCY": "5",
		"PF_EDP_GLOBAL_CONCURRENCY": "10", "PF_EDP_MAX_TENANT_BUCKETS": "10000",
		"PF_EDP_BUCKET_IDLE_TTL": "10m0s", "PF_EDP_ROLE_RECHECK": "5m0s", "PF_ALLOW_SUPERUSER_DSN": "0",
	}
	for name, def := range want {
		got, ok := doc.Flags[name]
		if !ok {
			t.Fatalf("%s missing from config/env-flags.json", name)
		}
		isDur := strings.HasPrefix(name, "PF_EDP_") &&
			!strings.Contains(name, "BYTES") && !strings.Contains(name, "RPM") &&
			!strings.Contains(name, "CONNS") && !strings.Contains(name, "CONCURRENCY") &&
			!strings.Contains(name, "BUCKETS") && name != "PF_EDP_ENFORCE_LIMITS"
		if isDur {
			gd, err1 := time.ParseDuration(got.Default)
			cd, err2 := time.ParseDuration(def)
			if err1 != nil || err2 != nil || gd != cd {
				t.Fatalf("%s default %q != code default %q", name, got.Default, def)
			}
			continue
		}
		if got.Default != def {
			t.Fatalf("%s default %q != code default %q", name, got.Default, def)
		}
	}
}
