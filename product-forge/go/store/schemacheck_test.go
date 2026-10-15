package store

import (
	"os"
	"path/filepath"
	"testing"
)

func TestExpectedFromDir(t *testing.T) {
	dir := t.TempDir()
	up := `CREATE TABLE tenants (
    id text PRIMARY KEY
);
CREATE INDEX idx_tenants_slug ON tenants (slug);
CREATE UNIQUE INDEX idx_projects_tenant ON projects (tenant_id, slug);
`
	down := `DROP TABLE tenants;`
	if err := os.WriteFile(filepath.Join(dir, "0002_core_schema.up.sql"), []byte(up), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "0002_core_schema.down.sql"), []byte(down), 0o600); err != nil {
		t.Fatal(err)
	}
	exp, err := ExpectedFromDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(exp.Tables) != 1 || exp.Tables[0] != "tenants" {
		t.Errorf("tables = %v", exp.Tables)
	}
	if len(exp.Indexes) != 2 {
		t.Errorf("indexes = %v", exp.Indexes)
	}
}

func TestMissing(t *testing.T) {
	missing := Missing([]string{"Tenants", "projects"}, []string{"tenants", "runs"})
	if len(missing) != 1 || missing[0] != "projects" {
		t.Errorf("missing = %v", missing)
	}
}
