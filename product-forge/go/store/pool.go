package store

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// PoolOptions configures the pgx connection pool for the PostgreSQL system of record (EDP-17 / BI-PF-1309).
type PoolOptions struct {
	MaxConns          int32
	MinConns          int32
	MaxConnLifetime   time.Duration
	MaxConnIdleTime   time.Duration
	HealthCheckPeriod time.Duration
	ConnectTimeout    time.Duration
}

// DefaultPoolOptions returns enterprise-sane defaults for a shared control-plane database.
func DefaultPoolOptions() PoolOptions {
	return PoolOptions{
		MaxConns:          10,
		MinConns:          1,
		MaxConnLifetime:   time.Hour,
		MaxConnIdleTime:   30 * time.Minute,
		HealthCheckPeriod: time.Minute,
		ConnectTimeout:    10 * time.Second,
	}
}

func (o PoolOptions) valid() bool {
	return o.MaxConns >= 1 && o.MinConns >= 0 && o.MinConns <= o.MaxConns
}

// OpenWithPool creates a pooled store with explicit options and verifies connectivity. Invalid options fall
// back to DefaultPoolOptions.
func OpenWithPool(ctx context.Context, dsn string, opts PoolOptions) (*PgStore, error) {
	if !opts.valid() {
		opts = DefaultPoolOptions()
	}
	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, err
	}
	cfg.MaxConns = opts.MaxConns
	cfg.MinConns = opts.MinConns
	cfg.MaxConnLifetime = opts.MaxConnLifetime
	cfg.MaxConnIdleTime = opts.MaxConnIdleTime
	cfg.HealthCheckPeriod = opts.HealthCheckPeriod
	if opts.ConnectTimeout > 0 {
		cfg.ConnConfig.ConnectTimeout = opts.ConnectTimeout
	}
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return nil, err
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, err
	}
	return &PgStore{pool: pool}, nil
}

// Stats reports pool saturation metrics for observability (EDP-22 consumers).
func (s *PgStore) Stats() map[string]int32 {
	st := s.pool.Stat()
	return map[string]int32{
		"acquired":     st.AcquiredConns(),
		"idle":         st.IdleConns(),
		"total":        st.TotalConns(),
		"max":          st.MaxConns(),
		"constructing": st.ConstructingConns(),
	}
}
