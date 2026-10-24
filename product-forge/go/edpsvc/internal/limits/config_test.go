package limits

import (
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
		c.DBTimeout != 5*time.Second || c.UploadTimeout != 120*time.Second || c.MigrationTimeout != 10*time.Minute ||
		c.MaxBodyBytes != 1<<20 || c.MaxUploadBytes != 64<<20 ||
		c.Pool.MaxConns != 10 || c.GlobalConcurrency != 10 || c.TenantRPM != 600 {
		t.Fatalf("unexpected defaults: %+v", c)
	}
}

func TestLoadEnvOverrides(t *testing.T) {
	c, err := Load(env(map[string]string{
		"PF_PROFILE": "production", "PF_EDP_ENFORCE_LIMITS": "1",
		"PF_EDP_REQUEST_TIMEOUT": "12s", "PF_EDP_DB_TIMEOUT": "2s", "PF_EDP_UPLOAD_TIMEOUT": "60s",
		"PF_EDP_READ_TIMEOUT": "120s", "PF_EDP_WRITE_TIMEOUT": "120s",
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
