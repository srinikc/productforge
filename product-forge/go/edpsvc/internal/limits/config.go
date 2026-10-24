// Package limits implements the EDP data-plane service guardrails (BI-PF-1302 / EDP-10): configurable
// timeouts, body/upload caps, per-tenant + global request/concurrency quotas, a versioned structured error
// envelope, request ids, metrics, and the production profile / runtime-role fail-closed checks.
//
// It is a leaf package: it depends only on the provider-neutral datastore port for the role check.
package limits

import (
	"fmt"
	"strconv"
	"strings"
	"time"
)

const (
	// ProfileDev is the default profile (local/dev).
	ProfileDev = "dev"
	// ProfileProduction refuses dev/anon auth, weak tokens and a superuser runtime role.
	ProfileProduction = "production"
)

// PoolConfig mirrors store.PoolOptions without importing the store package (keeps limits a leaf).
type PoolConfig struct {
	MaxConns          int32
	MinConns          int32
	MaxConnLifetime   time.Duration
	MaxConnIdleTime   time.Duration
	HealthCheckPeriod time.Duration
	ConnectTimeout    time.Duration
}

// Config is the effective guardrail configuration.
type Config struct {
	Profile string
	Enforce bool

	RequestTimeout    time.Duration
	DBTimeout         time.Duration
	UploadTimeout     time.Duration
	MigrationTimeout  time.Duration
	ReadHeaderTimeout time.Duration
	ReadTimeout       time.Duration
	WriteTimeout      time.Duration
	IdleTimeout       time.Duration

	MaxHeaderBytes int64
	MaxBodyBytes   int64
	MaxUploadBytes int64

	Pool PoolConfig

	TenantRPM         int
	GlobalRPM         int
	TenantConcurrency int
	GlobalConcurrency int
	MaxTenantBuckets  int
	BucketIdleTTL     time.Duration

	RoleRecheckInterval time.Duration
	AllowSuperuserDSN   bool
}

// Getenv is an environment accessor (os.Getenv in production, a map in tests).
type Getenv func(string) string

// DefaultConfig returns the safe defaults approved at Gate 1 (read/write are 180s so a 120s upload can finish;
// the per-request context still caps JSON at 30s).
func DefaultConfig() Config {
	return Config{
		Profile: ProfileDev, Enforce: true,
		RequestTimeout: 30 * time.Second, DBTimeout: 5 * time.Second, UploadTimeout: 120 * time.Second,
		MigrationTimeout:  150 * time.Second,
		ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 180 * time.Second, WriteTimeout: 180 * time.Second,
		IdleTimeout:    120 * time.Second,
		MaxHeaderBytes: 1 << 20, MaxBodyBytes: 1 << 20, MaxUploadBytes: 64 << 20,
		Pool: PoolConfig{MaxConns: 10, MinConns: 1, MaxConnLifetime: time.Hour, MaxConnIdleTime: 30 * time.Minute,
			HealthCheckPeriod: time.Minute, ConnectTimeout: 10 * time.Second},
		TenantRPM: 600, GlobalRPM: 6000, TenantConcurrency: 5, GlobalConcurrency: 10,
		MaxTenantBuckets: 10000, BucketIdleTTL: 10 * time.Minute,
		RoleRecheckInterval: 5 * time.Minute, AllowSuperuserDSN: false,
	}
}

func dur(v string, def time.Duration) (time.Duration, error) {
	v = strings.TrimSpace(v)
	if v == "" {
		return def, nil
	}
	if d, err := time.ParseDuration(v); err == nil {
		return d, nil
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return 0, fmt.Errorf("invalid duration %q", v)
	}
	return time.Duration(n) * time.Second, nil
}

func integer(v string, def int64) (int64, error) {
	v = strings.TrimSpace(v)
	if v == "" {
		return def, nil
	}
	n, err := strconv.ParseInt(v, 10, 64)
	if err != nil {
		return 0, fmt.Errorf("invalid integer %q", v)
	}
	return n, nil
}

func boolean(v string, def bool) bool {
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		return def
	}
}

// Load parses the PF_EDP_* configuration from getenv and validates it.
func Load(getenv Getenv) (Config, error) {
	if getenv == nil {
		return Config{}, fmt.Errorf("limits: getenv is required")
	}
	c := DefaultConfig()
	if p := strings.ToLower(strings.TrimSpace(getenv("PF_PROFILE"))); p != "" {
		c.Profile = p
	}
	c.Enforce = boolean(getenv("PF_EDP_ENFORCE_LIMITS"), true)
	c.AllowSuperuserDSN = boolean(getenv("PF_ALLOW_SUPERUSER_DSN"), false)

	var err error
	setDur := func(env string, dst *time.Duration) {
		if err != nil {
			return
		}
		*dst, err = dur(getenv(env), *dst)
		if err != nil {
			err = fmt.Errorf("%s: %w", env, err)
		}
	}
	setDur("PF_EDP_REQUEST_TIMEOUT", &c.RequestTimeout)
	setDur("PF_EDP_DB_TIMEOUT", &c.DBTimeout)
	setDur("PF_EDP_UPLOAD_TIMEOUT", &c.UploadTimeout)
	setDur("PF_EDP_MIGRATION_TIMEOUT", &c.MigrationTimeout)
	setDur("PF_EDP_READ_HEADER_TIMEOUT", &c.ReadHeaderTimeout)
	setDur("PF_EDP_READ_TIMEOUT", &c.ReadTimeout)
	setDur("PF_EDP_WRITE_TIMEOUT", &c.WriteTimeout)
	setDur("PF_EDP_IDLE_TIMEOUT", &c.IdleTimeout)
	setDur("PF_EDP_BUCKET_IDLE_TTL", &c.BucketIdleTTL)
	setDur("PF_EDP_ROLE_RECHECK", &c.RoleRecheckInterval)
	setDur("PF_EDP_POOL_CONNECT_TIMEOUT", &c.Pool.ConnectTimeout)
	setDur("PF_EDP_POOL_CONN_LIFETIME", &c.Pool.MaxConnLifetime)
	setDur("PF_EDP_POOL_CONN_IDLE", &c.Pool.MaxConnIdleTime)
	setDur("PF_EDP_POOL_HEALTH_PERIOD", &c.Pool.HealthCheckPeriod)

	setInt := func(env string, dst *int64) {
		if err != nil {
			return
		}
		*dst, err = integer(getenv(env), *dst)
		if err != nil {
			err = fmt.Errorf("%s: %w", env, err)
		}
	}
	var mb, mc, tc, gc, mtb int64 = int64(c.MaxBodyBytes), int64(c.MaxUploadBytes), int64(c.TenantRPM), int64(c.GlobalRPM), int64(c.MaxTenantBuckets)
	var tconc, gconc, poolMax, poolMin = int64(c.TenantConcurrency), int64(c.GlobalConcurrency), int64(c.Pool.MaxConns), int64(c.Pool.MinConns)
	var hdr int64 = c.MaxHeaderBytes
	setInt("PF_EDP_MAX_HEADER_BYTES", &hdr)
	setInt("PF_EDP_MAX_BODY_BYTES", &mb)
	setInt("PF_EDP_MAX_UPLOAD_BYTES", &mc)
	setInt("PF_EDP_TENANT_RPM", &tc)
	setInt("PF_EDP_GLOBAL_RPM", &gc)
	setInt("PF_EDP_TENANT_CONCURRENCY", &tconc)
	setInt("PF_EDP_GLOBAL_CONCURRENCY", &gconc)
	setInt("PF_EDP_POOL_MAX_CONNS", &poolMax)
	setInt("PF_EDP_POOL_MIN_CONNS", &poolMin)
	setInt("PF_EDP_MAX_TENANT_BUCKETS", &mtb)
	if err != nil {
		return Config{}, err
	}
	c.MaxHeaderBytes, c.MaxBodyBytes, c.MaxUploadBytes = hdr, mb, mc
	c.TenantRPM, c.GlobalRPM, c.TenantConcurrency, c.GlobalConcurrency = int(tc), int(gc), int(tconc), int(gconc)
	c.MaxTenantBuckets = int(mtb)
	c.Pool.MaxConns, c.Pool.MinConns = int32(poolMax), int32(poolMin)
	if err := c.Validate(); err != nil {
		return Config{}, err
	}
	return c, nil
}

// Validate fails closed on an inconsistent or unsafe configuration and names the offending setting.
func (c Config) Validate() error {
	if c.Profile != ProfileDev && c.Profile != ProfileProduction {
		return fmt.Errorf("PF_PROFILE=%q must be %q or %q", c.Profile, ProfileDev, ProfileProduction)
	}
	if c.Profile == ProfileProduction && !c.Enforce {
		return fmt.Errorf("PF_EDP_ENFORCE_LIMITS=0 is refused in the production profile")
	}
	if c.Profile == ProfileProduction && c.AllowSuperuserDSN {
		return fmt.Errorf("PF_ALLOW_SUPERUSER_DSN=1 is refused in the production profile")
	}
	if c.RequestTimeout <= 0 || c.DBTimeout <= 0 || c.UploadTimeout <= 0 || c.MigrationTimeout <= 0 || c.ReadHeaderTimeout <= 0 ||
		c.ReadTimeout <= 0 || c.WriteTimeout <= 0 || c.IdleTimeout <= 0 {
		return fmt.Errorf("all timeouts must be > 0")
	}
	if c.DBTimeout > c.RequestTimeout {
		return fmt.Errorf("PF_EDP_DB_TIMEOUT (%s) must be <= PF_EDP_REQUEST_TIMEOUT (%s)",
			c.DBTimeout, c.RequestTimeout)
	}
	if c.UploadTimeout < c.RequestTimeout {
		return fmt.Errorf("PF_EDP_UPLOAD_TIMEOUT (%s) must be >= PF_EDP_REQUEST_TIMEOUT (%s)",
			c.UploadTimeout, c.RequestTimeout)
	}
	if c.RequestTimeout > c.ReadTimeout || c.RequestTimeout > c.WriteTimeout {
		return fmt.Errorf("PF_EDP_REQUEST_TIMEOUT must be <= read/write server timeouts")
	}
	if c.UploadTimeout > c.ReadTimeout || c.UploadTimeout > c.WriteTimeout {
		return fmt.Errorf("PF_EDP_UPLOAD_TIMEOUT must be <= read/write server timeouts")
	}
	if c.MigrationTimeout > c.ReadTimeout || c.MigrationTimeout > c.WriteTimeout {
		return fmt.Errorf("PF_EDP_MIGRATION_TIMEOUT must be <= read/write server timeouts")
	}
	if c.MaxBodyBytes <= 0 || c.MaxUploadBytes < c.MaxBodyBytes || c.MaxHeaderBytes <= 0 {
		return fmt.Errorf("body/upload/header caps must be > 0 and upload >= body")
	}
	if c.Pool.MaxConns < 1 || c.Pool.MinConns < 0 || c.Pool.MinConns > c.Pool.MaxConns || c.Pool.ConnectTimeout <= 0 {
		return fmt.Errorf("invalid pool configuration (max>=1, 0<=min<=max, connect timeout>0)")
	}
	if c.GlobalConcurrency > int(c.Pool.MaxConns) {
		return fmt.Errorf("PF_EDP_GLOBAL_CONCURRENCY (%d) must be <= PF_EDP_POOL_MAX_CONNS (%d) so overload cannot deadlock the pool",
			c.GlobalConcurrency, c.Pool.MaxConns)
	}
	if c.TenantConcurrency < 1 || c.TenantConcurrency > c.GlobalConcurrency {
		return fmt.Errorf("tenant concurrency must be >=1 and <= global concurrency")
	}
	if c.TenantRPM < 1 || c.GlobalRPM < 1 || c.MaxTenantBuckets < 1 || c.BucketIdleTTL <= 0 {
		return fmt.Errorf("RPM, max tenant buckets and idle TTL must be > 0")
	}
	if c.RoleRecheckInterval < 0 {
		return fmt.Errorf("PF_EDP_ROLE_RECHECK must be >= 0")
	}
	return nil
}

var weakTokens = map[string]bool{"dev": true, "test": true, "changeme": true, "admin": true,
	"password": true, "secret": true, "pf": true, "token": true}

// ValidateProfile enforces the production auth posture (fail closed) and returns a clear error naming the
// offending setting. It does not read the DB role; see CheckDBRole.
func ValidateProfile(c Config, getenv Getenv) error {
	if c.Profile != ProfileProduction {
		return nil
	}
	for _, name := range []string{"PF_DEV", "API_ALLOW_ANON", "PF_ALLOW_ANON"} {
		if boolean(getenv(name), false) {
			return fmt.Errorf("production profile refuses development auth: %s is enabled", name)
		}
	}
	tok := strings.TrimSpace(getenv("PF_ADMIN_TOKEN"))
	if tok == "" {
		return fmt.Errorf("production profile requires PF_ADMIN_TOKEN")
	}
	if len(tok) < 24 {
		return fmt.Errorf("production profile requires PF_ADMIN_TOKEN of at least 24 characters")
	}
	if weakTokens[strings.ToLower(tok)] {
		return fmt.Errorf("production profile refuses the default/weak PF_ADMIN_TOKEN")
	}
	return nil
}
