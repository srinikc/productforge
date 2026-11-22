package dualvec

import (
	"fmt"
	"strings"

	"productforge/datastore"
)

// EngineType identifies the underlying vector storage engine.
type EngineType string

const (
	EngineSQLite   EngineType = "sqlite"
	EnginePostgres EngineType = "postgres"
)

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
