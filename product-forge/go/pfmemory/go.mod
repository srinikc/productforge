module productforge/pfmemory

go 1.26.0

require (
	productforge/datastore v0.0.0
	productforge/memory v0.0.0
)

require github.com/google/uuid v1.6.0 // indirect

replace productforge/datastore => ../datastore

replace productforge/memory => ../memory
