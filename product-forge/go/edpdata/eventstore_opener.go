package edpdata

import (
	"context"
	"fmt"
	"os"

	"productforge/store"
)

// OpenEventStoreFromEnv opens the event store from PF_DB_DSN.
// The DSN is process configuration only; it is never accepted from event payloads.
func OpenEventStoreFromEnv(ctx context.Context) (*EventStore, func(), error) {
	dsn := os.Getenv("PF_DB_DSN")
	if dsn == "" {
		return nil, nil, fmt.Errorf("PF_DB_DSN is required for the event authority")
	}
	pg, err := store.Open(ctx, dsn)
	if err != nil {
		return nil, nil, err
	}
	return NewEventStore(pg), pg.Close, nil
}
