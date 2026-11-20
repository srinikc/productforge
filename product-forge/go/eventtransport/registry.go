package eventtransport

import "productforge/edpdata"

// Registry selects a transport by subscription transport name.
type Registry struct {
	transports map[string]edpdata.Transport
	tenants    map[string]map[string]edpdata.Transport
}

func NewRegistry() *Registry {
	return &Registry{transports: map[string]edpdata.Transport{}, tenants: map[string]map[string]edpdata.Transport{}}
}
func (r *Registry) Register(name string, t edpdata.Transport) {
	if name != "" && t != nil {
		r.transports[name] = t
	}
}
func (r *Registry) Get(name string) (edpdata.Transport, bool) {
	t, ok := r.transports[name]
	return t, ok
}

// RegisterForTenant binds a transport to a tenant.
func (r *Registry) RegisterForTenant(tenant, name string, t edpdata.Transport) {
	if tenant == "" || name == "" || t == nil {
		return
	}
	if r.tenants[tenant] == nil {
		r.tenants[tenant] = map[string]edpdata.Transport{}
	}
	r.tenants[tenant][name] = t
}

// GetForTenant rejects empty or unbound tenant lookups.
func (r *Registry) GetForTenant(tenant, name string) (edpdata.Transport, bool) {
	if tenant == "" {
		return nil, false
	}
	t, ok := r.tenants[tenant][name]
	return t, ok
}

// DefaultRegistry builds the standard transports, including webhook; missing keys fail at delivery.
func DefaultRegistry() *Registry {
	r := NewRegistry()
	r.Register("inproc", NewInproc())
	r.Register("webhook", NewWebhook())
	r.Register("notify", NewNotify())
	return r
}
