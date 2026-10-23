// Package objreconcile compares a manifest to the object store and reports drift (EDP-16).
//
// The scanner is READ-ONLY: it never deletes or repairs. Checksums are sha256 (the store's own content
// checksum; never an S3 ETag). Reports are deterministic: arrays are sorted and the schema is versioned.
package objreconcile

import (
	"context"
	"log"
	"sort"
	"strings"

	"productforge/datastore"
)

const Schema = "pf.objreconcile/2"

// Entry is one expected object.
type Entry struct {
	Key      string
	Size     int64
	Checksum string // sha256 hex; empty = size-only comparison
}

// Report is the deterministic drift report.
type Report struct {
	Schema               string   `json:"schema"`
	Prefix               string   `json:"prefix"`
	Expected             int      `json:"expected"`
	Actual               int      `json:"actual"`
	Invalid              []string `json:"invalid"` // out-of-prefix/duplicate manifest entries
	Missing              []string `json:"missing"`
	Orphaned             []string `json:"orphaned"`
	SizeMismatch         []string `json:"size_mismatch"`
	ChecksumMismatch     []string `json:"checksum_mismatch"`
	ChecksumUnverifiable []string `json:"checksum_unverifiable"` // manifest has a digest but the store cannot provide one
}

// Clean reports whether the manifest and the store agree (unverifiable checksums are NOT clean).
func (r Report) Clean() bool {
	return len(r.Invalid)+len(r.Missing)+len(r.Orphaned)+
		len(r.SizeMismatch)+len(r.ChecksumMismatch)+len(r.ChecksumUnverifiable) == 0
}

// Scan lists the store under prefix and compares every expected key via Head (authoritative fields).
func Scan(ctx context.Context, store datastore.ObjectStore, prefix string, manifest []Entry) (Report, error) {
	rep := Report{Schema: Schema, Prefix: prefix, Expected: len(manifest),
		Invalid: []string{}, Missing: []string{}, Orphaned: []string{},
		SizeMismatch: []string{}, ChecksumMismatch: []string{}, ChecksumUnverifiable: []string{}}
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
		if _, dup := want[e.Key]; dup {
			rep.Invalid = append(rep.Invalid, e.Key)
			continue
		}
		if !strings.HasPrefix(e.Key, prefix) {
			rep.Invalid = append(rep.Invalid, e.Key)
			continue
		}
		want[e.Key] = e
	}
	for _, e := range want {
		head, err := store.Head(ctx, e.Key)
		if err != nil {
			rep.Missing = append(rep.Missing, e.Key)
			continue
		}
		if head.Size != e.Size {
			rep.SizeMismatch = append(rep.SizeMismatch, e.Key)
		}
		if e.Checksum != "" {
			switch {
			case head.Checksum == "":
				rep.ChecksumUnverifiable = append(rep.ChecksumUnverifiable, e.Key)
			case !strings.EqualFold(head.Checksum, e.Checksum):
				rep.ChecksumMismatch = append(rep.ChecksumMismatch, e.Key)
			}
		}
	}
	for k := range actual {
		if _, ok := want[k]; !ok {
			rep.Orphaned = append(rep.Orphaned, k)
		}
	}
	sort.Strings(rep.Invalid)
	sort.Strings(rep.Missing)
	sort.Strings(rep.Orphaned)
	sort.Strings(rep.SizeMismatch)
	sort.Strings(rep.ChecksumMismatch)
	sort.Strings(rep.ChecksumUnverifiable)
	if !rep.Clean() {
		log.Printf("objreconcile: drift prefix=%q missing=%d orphaned=%d size=%d checksum=%d unverifiable=%d invalid=%d",
			prefix, len(rep.Missing), len(rep.Orphaned), len(rep.SizeMismatch),
			len(rep.ChecksumMismatch), len(rep.ChecksumUnverifiable), len(rep.Invalid))
	}
	return rep, nil
}
