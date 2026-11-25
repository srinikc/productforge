package eventtransport

import (
	"context"
	"sync"

	"productforge/edpdata"
)

// Inproc delivers to same-process callbacks.
type Inproc struct {
	mu        sync.RWMutex
	callbacks map[string][]func(context.Context, edpdata.Event) error
}

func NewInproc() *Inproc {
	return &Inproc{callbacks: map[string][]func(context.Context, edpdata.Event) error{}}
}
func (i *Inproc) On(eventType string, fn func(context.Context, edpdata.Event) error) {
	i.mu.Lock()
	defer i.mu.Unlock()
	i.callbacks[eventType] = append(i.callbacks[eventType], fn)
}
func (i *Inproc) Deliver(ctx context.Context, _ edpdata.Subscription, ev edpdata.Event) error {
	i.mu.RLock()
	cbs := append([]func(context.Context, edpdata.Event) error(nil), i.callbacks[ev.Type]...)
	i.mu.RUnlock()
	for _, fn := range cbs {
		if err := fn(ctx, ev); err != nil {
			return err
		}
	}
	return nil
}
