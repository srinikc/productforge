// Package objreconcile compares a manifest to the object store and reports drift (EDP-16).
//
// The scanner is READ-ONLY: it never deletes or repairs. Checksums are sha256 (the store's own content
// checksum; never an S3 ETag). Reports are deterministic: arrays are sorted and the schema is versioned.
package objreconcile

import (
	"context"
	"encoding/hex"
	"errors"
	"fmt"
	"log"
	"os"
	"sort"
	"strings"
	"sync"

	"productforge/datastore"
)

const Schema = "pf.objreconcile/1"

// MaxObjects bounds a single scan (fail closed rather than OOM on bucket-scale listings).
const MaxObjects = 100000

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
	Provided             int      `json:"provided"`
	Expected             int      `json:"expected"` // valid entries after invalid/duplicate filtering
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
	prefix = normalizePrefix(prefix)
	rep := Report{Schema: Schema, Prefix: prefix, Provided: len(manifest),
		Invalid: []string{}, Missing: []string{}, Orphaned: []string{},
		SizeMismatch: []string{}, ChecksumMismatch: []string{}, ChecksumUnverifiable: []string{}}
	var objects []datastore.ObjectInfo
	if pl, ok := store.(datastore.PrefixLister); ok {
		marker := ""
		for {
			page, next, err := pl.ListPage(ctx, prefix, marker, 1000)
			if err != nil {
				return rep, err
			}
			objects = append(objects, page...)
			if len(objects) > MaxObjects {
				return rep, fmt.Errorf("objreconcile: more than %d objects exceed the scan bound", MaxObjects)
			}
			if next == "" || len(page) == 0 {
				break
			}
			marker = next
		}
	} else {
		var err error
		objects, err = store.List(ctx, prefix)
		if err != nil {
			return rep, err
		}
		if len(objects) > MaxObjects {
			return rep, fmt.Errorf("objreconcile: %d objects exceed the scan bound (%d)", len(objects), MaxObjects)
		}
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
		if !strings.HasPrefix(e.Key, prefix) || !validChecksum(e.Checksum) {
			rep.Invalid = append(rep.Invalid, e.Key)
			continue
		}
		want[e.Key] = e
	}
	rep.Expected = len(want)
	// Head only entries whose digest is needed and missing from List; bounded concurrency (8).
	type headResult struct {
		key  string
		info datastore.ObjectInfo
		err  error
	}
	var need []string
	for _, e := range want {
		info, ok := actual[e.Key]
		if ok && e.Checksum != "" && info.Checksum == "" {
			need = append(need, e.Key)
		}
	}
	heads := make(map[string]datastore.ObjectInfo, len(need))
	if len(need) > 0 {
		workers := 8
		if len(need) < workers {
			workers = len(need)
		}
		jobs := make(chan string)
		out := make(chan headResult, len(need))
		var wg sync.WaitGroup
		for i := 0; i < workers; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				for key := range jobs {
					info, err := store.Head(ctx, key)
					out <- headResult{key: key, info: info, err: err}
				}
			}()
		}
		go func() {
			for _, key := range need {
				jobs <- key
			}
			close(jobs)
			wg.Wait()
			close(out)
		}()
		for r := range out {
			if r.err != nil && !notFound(r.err) {
				return rep, r.err // fail closed: transient/permission errors are not drift
			}
			if r.err == nil {
				heads[r.key] = r.info
			}
		}
	}
	for _, e := range want {
		info, ok := actual[e.Key]
		if !ok {
			rep.Missing = append(rep.Missing, e.Key)
			continue
		}
		if h, ok := heads[e.Key]; ok {
			info = h
		}
		if info.Size != e.Size {
			rep.SizeMismatch = append(rep.SizeMismatch, e.Key)
		}
		if e.Checksum != "" {
			switch {
			case info.Checksum == "":
				rep.ChecksumUnverifiable = append(rep.ChecksumUnverifiable, e.Key)
			case !strings.EqualFold(info.Checksum, e.Checksum):
				rep.ChecksumMismatch = append(rep.ChecksumMismatch, e.Key)
			}
		}
	}
	invalid := make(map[string]bool, len(rep.Invalid))
	for _, k := range rep.Invalid {
		invalid[k] = true
	}
	for k := range actual {
		if _, ok := want[k]; !ok && !invalid[k] {
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

// validChecksum accepts empty (size-only) or a 32-byte hex sha256 digest.
func validChecksum(s string) bool {
	if s == "" {
		return true
	}
	if len(s) != 64 {
		return false
	}
	_, err := hex.DecodeString(s)
	return err == nil
}

// normalizePrefix makes a prefix a directory boundary ("p" -> "p/", "p/" unchanged).
func normalizePrefix(p string) string {
	p = strings.TrimSpace(p)
	if p == "" || strings.HasSuffix(p, "/") {
		return p
	}
	return p + "/"
}

// notFound distinguishes true absence from transient/permission errors.
func notFound(err error) bool {
	if errors.Is(err, os.ErrNotExist) {
		return true
	}
	return false
}
