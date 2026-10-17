package residency

import (
	"os"
	"path/filepath"
	"testing"
)

// profilesDir is the shipped config (product-forge/config/residency-profiles) from this package's dir.
const profilesDir = "../../../../config/residency-profiles"

func TestShippedProfilesLoadAndValidate(t *testing.T) {
	r, err := LoadDir(profilesDir)
	if err != nil {
		t.Fatalf("load shipped profiles: %v", err)
	}
	for _, region := range []string{"IN", "US"} {
		p, err := r.Resolve(region)
		if err != nil {
			t.Fatalf("resolve %s: %v", region, err)
		}
		if p.Region != region || p.ID == "" || p.Version == "" {
			t.Fatalf("bad policy for %s: %+v", region, p)
		}
		if !p.EncryptionAtRest || !p.EncryptionInTransit {
			t.Fatalf("%s: encryption flags must be set (counsel content)", region)
		}
	}
	if got := r.Regions(); len(got) != 2 {
		t.Fatalf("regions = %v, want [IN US]", got)
	}
}

func TestResolveIsFailClosedOnUnknownRegion(t *testing.T) {
	r, err := LoadDir(profilesDir)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := r.Resolve("ZZ"); err == nil {
		t.Fatal("unknown region must fail closed")
	} else if !isUnknown(err) {
		t.Fatalf("want ErrUnknownRegion, got %v", err)
	}
	if _, err := r.Resolve(""); err == nil {
		t.Fatal("empty region must fail closed")
	}
}

func TestLatestVersionWins(t *testing.T) {
	dir := t.TempDir()
	write(t, dir, "p1.json", `{"id":"us-v1","version":"1.0","region":"US","residency":"in-region","cross_border_transfer":"conditioned","allowed_regions":["US"]}`)
	write(t, dir, "p2.json", `{"id":"us-v2","version":"2.0","region":"US","residency":"in-region","cross_border_transfer":"allowed","allowed_regions":["US"]}`)
	r, err := LoadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	p, err := r.Resolve("US")
	if err != nil || p.Version != "2.0" {
		t.Fatalf("latest version: %+v err=%v", p, err)
	}
	if vs := r.Versions("US"); len(vs) != 2 || vs[0] != "1.0" || vs[1] != "2.0" {
		t.Fatalf("versions = %v", vs)
	}
}

func TestLoadDirFailsClosedOnInvalidOrEmpty(t *testing.T) {
	// missing required field -> error (fail-closed)
	dir := t.TempDir()
	write(t, dir, "bad.json", `{"id":"x","version":"1.0"}`)
	if _, err := LoadDir(dir); err == nil {
		t.Fatal("invalid profile must fail closed")
	}
	// empty dir -> error (an empty registry cannot be trusted)
	if _, err := LoadDir(t.TempDir()); err == nil {
		t.Fatal("empty profiles dir must fail closed")
	}
	// bad version -> error
	dir2 := t.TempDir()
	write(t, dir2, "bad2.json", `{"id":"y","version":"vX","region":"US","residency":"in-region","cross_border_transfer":"allowed","allowed_regions":["US"]}`)
	if _, err := LoadDir(dir2); err == nil {
		t.Fatal("bad version must fail closed")
	}
}

func write(t *testing.T, dir, name, body string) {
	t.Helper()
	if err := os.WriteFile(filepath.Join(dir, name), []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
}

func isUnknown(err error) bool {
	for e := err; e != nil; {
		if e == ErrUnknownRegion {
			return true
		}
		u, ok := e.(interface{ Unwrap() error })
		if !ok {
			break
		}
		e = u.Unwrap()
	}
	return false
}
