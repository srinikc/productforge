package dualvec

import (
	"fmt"
	"log"
	"strings"
	"time"

	"productforge/datastore"
)

// EngineType identifies the underlying vector storage engine.
type EngineType string

const (
	EngineSQLite   EngineType = "sqlite"
	EnginePostgres EngineType = "postgres"
)

// Observer receives events for dualvec storage operations.
type Observer interface {
	Observe(engine EngineType, op string, tenant string, project string, duration time.Duration, err error)
}

type defaultObserver struct{}

func (defaultObserver) Observe(engine EngineType, op string, tenant string, project string, duration time.Duration, err error) {
	status := "ok"
	if err != nil {
		status = "error"
	}
	log.Printf("[dualvec] engine=%s op=%s tenant=%s project=%s duration_ms=%d status=%s err=%v",
		engine, op, tenant, project, duration.Milliseconds(), status, err)
}

var currentObserver Observer = defaultObserver{}

// SetObserver configures the package-level observer.
func SetObserver(o Observer) {
	if o == nil {
		currentObserver = defaultObserver{}
		return
	}
	currentObserver = o
}

// Config holds initialization parameters for the dual-engine vector store.
type Config struct {
	// DSN defines the connection string or file path:
	// - "sqlite://path/to/db.sqlite", "file:data.db", ":memory:" -> SQLite backend
	// - "postgres://...", "postgresql://..." -> PostgreSQL pgvector backend
	DSN string

	// RelationalStore is an optional pre-existing PostgreSQL connection pool.
	RelationalStore datastore.RelationalStore

	// Dimension defines the embedding dimension (defaults to 1536).
	Dimension int

	// Observer is an optional telemetry observer for operations.
	Observer Observer
}

// DetectEngine inspects a connection string and returns the target engine type.
func DetectEngine(dsn string) EngineType {
	lower := strings.ToLower(strings.TrimSpace(dsn))
	if strings.HasPrefix(lower, "postgres://") || strings.HasPrefix(lower, "postgresql://") {
		return EnginePostgres
	}
	return EngineSQLite
}

// New creates and initializes a unified datastore.MemoryRepository based on configuration.
func New(cfg Config) (datastore.MemoryRepository, error) {
	if cfg.Dimension <= 0 {
		cfg.Dimension = EmbeddingDim
	}
	if cfg.Observer != nil {
		SetObserver(cfg.Observer)
	}

	engine := DetectEngine(cfg.DSN)
	if cfg.RelationalStore != nil {
		engine = EnginePostgres
	}

	switch engine {
	case EnginePostgres:
		if cfg.RelationalStore == nil {
			return nil, fmt.Errorf("dualvec: postgres engine requires RelationalStore instance")
		}
		return NewPgMemoryStore(cfg.RelationalStore), nil

	case EngineSQLite:
		return NewSqliteMemoryStore(cfg.DSN)

	default:
		return nil, fmt.Errorf("dualvec: unsupported engine type %q", engine)
	}
}
