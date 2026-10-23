package objreconcile

import (
	"context"
	"io"
	"testing"
	"time"

	"productforge/datastore"
)

type fakeStore struct{ objects []datastore.ObjectInfo }

func (f fakeStore) Put(context.Context, string, io.Reader, int64, datastore.PutOptions) (datastore.ObjectInfo, error) {
	return datastore.ObjectInfo{}, nil
}
func (f fakeStore) Get(context.Context, string, string) (io.ReadCloser, datastore.ObjectInfo, error) {
	return nil, datastore.ObjectInfo{}, nil
}
func (f fakeStore) Head(context.Context, string) (datastore.ObjectInfo, error) {
	return datastore.ObjectInfo{}, nil
}
func (f fakeStore) Delete(context.Context, string, string) error { return nil }
func (f fakeStore) List(context.Context, string) ([]datastore.ObjectInfo, error) {
	return f.objects, nil
}
func (f fakeStore) SignedURL(context.Context, string, string, time.Duration) (string, error) {
	return "", nil
}
func (f fakeStore) Capabilities() datastore.Capabilities { return datastore.Capabilities{} }

func TestScanClean(t *testing.T) {
	st := fakeStore{objects: []datastore.ObjectInfo{{Key: "p/a", Size: 3, Checksum: "aa"}}}
	rep, err := Scan(context.Background(), st, "p/", []Entry{{Key: "p/a", Size: 3, Checksum: "aa"}})
	if err != nil {
		t.Fatal(err)
	}
	if !rep.Clean() {
		t.Fatalf("expected clean, got %+v", rep)
	}
}

func TestScanDetectsDrift(t *testing.T) {
	st := fakeStore{objects: []datastore.ObjectInfo{
		{Key: "p/a", Size: 4, Checksum: "bb"}, // size + checksum mismatch
		{Key: "p/orphan", Size: 1, Checksum: "cc"},
	}}
	rep, err := Scan(context.Background(), st, "p/", []Entry{
		{Key: "p/a", Size: 3, Checksum: "aa"},
		{Key: "p/missing", Size: 1, Checksum: "dd"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if rep.Clean() || len(rep.Missing) != 1 || rep.Missing[0] != "p/missing" ||
		len(rep.Orphaned) != 1 || rep.Orphaned[0] != "p/orphan" ||
		len(rep.SizeMismatch) != 1 || len(rep.ChecksumMismatch) != 1 {
		t.Fatalf("drift report wrong: %+v", rep)
	}
}
