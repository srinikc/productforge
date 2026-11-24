package pfmemory

import "time"

// Observer receives bounded operation signals. Implementations must never change policy outcomes.
type Observer interface {
	Observe(op string, result string, duration time.Duration)
	Denied(reason string)
	FilteredProjectless()
}

type noopObserver struct{}

func (noopObserver) Observe(string, string, time.Duration) {}
func (noopObserver) Denied(string)                         {}
func (noopObserver) FilteredProjectless()                  {}

// ObserverFuncs lets callers adapt an existing metrics registry without importing one here.
type ObserverFuncs struct {
	ObserveFn   func(op string, result string, duration time.Duration)
	DeniedFn    func(reason string)
	FilteredFn  func()
}

func (o ObserverFuncs) Observe(op string, result string, duration time.Duration) {
	if o.ObserveFn != nil {
		o.ObserveFn(op, result, duration)
	}
}

func (o ObserverFuncs) Denied(reason string) {
	if o.DeniedFn != nil {
		o.DeniedFn(reason)
	}
}

func (o ObserverFuncs) FilteredProjectless() {
	if o.FilteredFn != nil {
		o.FilteredFn()
	}
}
