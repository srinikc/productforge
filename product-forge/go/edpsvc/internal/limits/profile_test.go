package limits

import (
	"context"
	"os"
	"testing"

	"productforge/store"
)

func TestRoleViolation(t *testing.T) {
	if !(Role{Superuser: true}).Violation(false) {
		t.Fatal("superuser must violate by default")
	}
	if !(Role{BypassRLS: true}).Violation(false) {
		t.Fatal("bypassrls must violate by default")
	}
	if (Role{Superuser: true}).Violation(true) {
		t.Fatal("allowSuperuser must permit an explicit escape hatch")
	}
	if (Role{Name: "pf_app"}).Violation(false) {
		t.Fatal("a normal role must not violate")
	}
}

func TestCheckDBRoleIntegration(t *testing.T) {
	dsn := os.Getenv("PF_RUNTIME_DSN")
	if dsn == "" {
		t.Skip("set PF_RUNTIME_DSN (non-BYPASSRLS role) to run the runtime role check")
	}
	ctx := context.Background()
	st, err := store.Open(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer st.Close()
	r, err := CheckDBRole(ctx, st, false)
	if err != nil {
		t.Fatalf("pf_app/pf_runtime must pass: %v", err)
	}
	if r.Name == "" || r.Superuser || r.BypassRLS {
		t.Fatalf("unexpected role %+v", r)
	}
}
