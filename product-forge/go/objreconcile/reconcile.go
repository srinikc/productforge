// Package objreconcile compares a manifest to the object store and reports drift (EDP-16).
//
// The scanner is READ-ONLY: it never deletes or repairs. Checksums are sha256 (the store's own content
// checksum; never an S3 ETag). Reports are deterministic: arrays are sorted and the schema is versioned.
package objreconcile

import (
	"context"
	"sort"
	"strings"

	"productforge/datastore"
)

const Schema = "pf.objreconcile/1"

// Entry is one expected object.
type Entry struct {
	Key      string
	Size     int64
	Checksum string // sha256 hex; empty = size-only comparison
}

// Report is the deterministic drift report.
type Report struct {
	Schema           string   `json:"schema"`
	Prefix           string   `json:"prefix"`
	Expected         int      `json:"expected"`
	Actual           int      `json:"actual"`
	Missing          []string `json:"missing"`
	Orphaned         []string `json:"orphaned"`
	SizeMismatch     []string `json:"size_mismatch"`
	ChecksumMismatch []string `json:"checksum_mismatch"`
}

// Clean reports whether the manifest and the store agree.
func (r Report) Clean() bool {
	return len(r.Missing)+len(r.Orphaned)+len(r.SizeMismatch)+len(r.ChecksumMismatch) == 0
}

// Scan lists the store under prefix and compares it with manifest.
func Scan(ctx context.Context, store datastore.ObjectStore, prefix string, manifest []Entry) (Report, error) {
	rep := Report{Schema: Schema, Prefix: prefix, Expected: len(manifest),
		Missing: []string{}, Orphaned: []string{}, SizeMismatch: []string{}, ChecksumMismatch: []string{}}
	objects, err := store.List(ctx, prefix)
	if err != nil {
		return rep, err
	}
	rep.Actual = len(objects)
	actual := make(map[string]datastore.ObjectInfo, len(objects))
	for _, o := range objects {
		actual[o.Key] = o
	}
	want := make(map[string]Entry, len(manifest))
	for _, e := range manifest {
		if !strings.HasPrefix(e.Key, prefix) {
			rep.Missing = append(rep.Missing, e.Key)
			continue
		}
		want[e.Key] = e
		got, ok := actual[e.Key]
		if !ok {
			rep.Missing = append(rep.Missing, e.Key)
			continue
		}
		if got.Size != e.Size {
			rep.SizeMismatch = append(rep.SizeMismatch, e.Key)
		}
		if e.Checksum != "" && got.Checksum != "" && !strings.EqualFold(got.Checksum, e.Checksum) {
			rep.ChecksumMismatch = append(rep.ChecksumMismatch, e.Key)
		}
	}
	for k := range actual {
		if _, ok := want[k]; !ok {
			rep.Orphaned = append(rep.Orphaned, k)
		}
	}
	sort.Strings(rep.Missing)
	sort.Strings(rep.Orphaned)
	sort.Strings(rep.SizeMismatch)
	sort.Strings(rep.ChecksumMismatch)
	return rep, nil
}
