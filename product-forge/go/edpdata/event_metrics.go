package edpdata

// EventMetrics is the observability owner for event authority signals.
// Implementations must be safe for concurrent use.
type EventMetrics interface {
	OutboxRows(tenant, status string, count int64)
	OutboxBoundExceeded(tenant string)
	OutboxPruned(tenant string, count int64)
	ProjectionFailed(tenant string)
	DeliveryDelivered(tenant, subscription string)
	DeliveryRetried(tenant, subscription string)
	DeliveryDeadLettered(tenant, subscription string)
	DeliverySkipped(tenant, subscription string)
}

type nopEventMetrics struct{}

func (nopEventMetrics) OutboxRows(string, string, int64)    {}
func (nopEventMetrics) OutboxBoundExceeded(string)          {}
func (nopEventMetrics) OutboxPruned(string, int64)          {}
func (nopEventMetrics) ProjectionFailed(string)             {}
func (nopEventMetrics) DeliveryDelivered(string, string)    {}
func (nopEventMetrics) DeliveryRetried(string, string)      {}
func (nopEventMetrics) DeliveryDeadLettered(string, string) {}
func (nopEventMetrics) DeliverySkipped(string, string)      {}

// WithMetrics attaches the observability owner.
func (s *EventStore) WithMetrics(m EventMetrics) *EventStore {
	if m != nil {
		s.metrics = m
	}
	return s
}

// RecordProjectionFailure emits a projection failure through the metrics owner.
func (s *EventStore) RecordProjectionFailure(tenant string) {
	s.metrics.ProjectionFailed(tenant)
}
