package eventtransport

import "productforge/edpdata"

// Registry selects a transport by subscription transport name.
type Registry struct{ transports map[string]edpdata.Transport }

func NewRegistry() *Registry { return &Registry{transports: map[string]edpdata.Transport{}} }
func (r *Registry) Register(name string, t edpdata.Transport) {
	if name != "" && t != nil {
		r.transports[name] = t
	}
}
func (r *Registry) Get(name string) (edpdata.Transport, bool) {
	t, ok := r.transports[name]
	return t, ok
}

// GetForTenant rejects empty tenant lookups; transport selection stays tenant-scoped.
func (r *Registry) GetForTenant(tenant, name string) (edpdata.Transport, bool) {
	if tenant == "" {
		return nil, false
	}
	return r.Get(name)
}

// DefaultRegistry builds the standard transports. Missing optional config disables only that transport.
func DefaultRegistry() *Registry {
	r := NewRegistry()
	r.Register("inproc", NewInproc())
	if _, ok := ResolveHMACKey(""); ok {
		r.Register("webhook", NewWebhook())
	}
	r.Register("notify", NewNotify())
	return r
}
