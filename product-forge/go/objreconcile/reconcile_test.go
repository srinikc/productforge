package objreconcile

import (
	"context"
	"errors"
	"io"
	"os"
	"strings"
	"testing"
	"time"

	"productforge/datastore"
)

type fakeStore struct {
	objects map[string]datastore.ObjectInfo
}

func (f fakeStore) Put(context.Context, string, io.Reader, int64, datastore.PutOptions) (datastore.ObjectInfo, error) {
	return datastore.ObjectInfo{}, nil
}
func (f fakeStore) Get(context.Context, string, string) (io.ReadCloser, datastore.ObjectInfo, error) {
	return nil, datastore.ObjectInfo{}, nil
}
func (f fakeStore) Head(_ context.Context, key string) (datastore.ObjectInfo, error) {
	o, ok := f.objects[key]
	if !ok {
		return datastore.ObjectInfo{}, os.ErrNotExist
	}
	return o, nil
}
func (f fakeStore) Delete(context.Context, string, string) error { return nil }
func (f fakeStore) List(context.Context, string) ([]datastore.ObjectInfo, error) {
	out := make([]datastore.ObjectInfo, 0, len(f.objects))
	for _, o := range f.objects {
		out = append(out, o)
	}
	return out, nil
}
func (f fakeStore) SignedURL(context.Context, string, string, time.Duration) (string, error) {
	return "", nil
}
func (f fakeStore) Capabilities() datastore.Capabilities { return datastore.Capabilities{} }

func TestScanClean(t *testing.T) {
	st := fakeStore{objects: map[string]datastore.ObjectInfo{
		"p/a": {Key: "p/a", Size: 3, Checksum: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
	}}
	rep, err := Scan(context.Background(), st, "p/", []Entry{{Key: "p/a", Size: 3, Checksum: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}})
	if err != nil {
		t.Fatal(err)
	}
	if !rep.Clean() {
		t.Fatalf("expected clean, got %+v", rep)
	}
}

func TestScanDetectsDrift(t *testing.T) {
	st := fakeStore{objects: map[string]datastore.ObjectInfo{
		"p/a":      {Key: "p/a", Size: 4, Checksum: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},
		"p/orphan": {Key: "p/orphan", Size: 1, Checksum: "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"},
		"p/noSum":  {Key: "p/noSum", Size: 2},
	}}
	rep, err := Scan(context.Background(), st, "p/", []Entry{
		{Key: "p/a", Size: 3, Checksum: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
		{Key: "p/missing", Size: 1, Checksum: "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"},
		{Key: "p/noSum", Size: 2, Checksum: "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"},
		{Key: "q/out", Size: 1},
		{Key: "p/a", Size: 3},
	})
	if err != nil {
		t.Fatal(err)
	}
	if rep.Clean() {
		t.Fatalf("expected drift, got clean: %+v", rep)
	}
	if len(rep.Missing) != 1 || rep.Missing[0] != "p/missing" ||
		len(rep.Orphaned) != 1 || rep.Orphaned[0] != "p/orphan" ||
		len(rep.SizeMismatch) != 1 || rep.SizeMismatch[0] != "p/a" ||
		len(rep.ChecksumMismatch) != 1 || rep.ChecksumMismatch[0] != "p/a" ||
		len(rep.ChecksumUnverifiable) != 1 || rep.ChecksumUnverifiable[0] != "p/noSum" ||
		len(rep.Invalid) != 2 {
		t.Fatalf("drift report wrong: %+v", rep)
	}
}

func TestScanAbortsOnTransientHeadError(t *testing.T) {
	st := fakeStore{objects: map[string]datastore.ObjectInfo{"p/a": {Key: "p/a", Size: 1}}}
	st.objects["p/a"] = datastore.ObjectInfo{Key: "p/a", Size: 1, Checksum: ""}
	// Manifest needs a digest, but Head fails transiently -> Scan must abort, not report drift.
	bad := fakeStore{objects: map[string]datastore.ObjectInfo{"p/a": {Key: "p/a", Size: 1}}}
	badHead := headErrStore{bad}
	if _, err := Scan(context.Background(), badHead, "p/", []Entry{{Key: "p/a", Size: 1, Checksum: strings.Repeat("a", 64)}}); err == nil {
		t.Fatal("transient Head error must abort the scan")
	}
	_ = st
}

type headErrStore struct{ fakeStore }

func (h headErrStore) Head(context.Context, string) (datastore.ObjectInfo, error) {
	return datastore.ObjectInfo{}, errors.New("access denied")
}
