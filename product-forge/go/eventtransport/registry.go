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
