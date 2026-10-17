package datastore

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"time"
)

// ConformObjectStore runs the shared ObjectStore conformance suite against an adapter. It returns a slice
// of failures (empty == conformant). Adapters (local FS, S3-compatible, ...) MUST pass this suite; it is the
// contract that lets domain code swap providers without change (ADR-0006).
//
// The probe key is UNIQUE per run so it can never clobber a real object; and a DECLARED capability must
// actually work (capability honesty) - a false claim fails the suite.
func ConformObjectStore(ctx context.Context, s ObjectStore) []error {
	var errs []error
	key := fmt.Sprintf("pf/conformance/probe-%d", time.Now().UnixNano())
	body := []byte("conformance probe")

	info, err := s.Put(ctx, key, bytes.NewReader(body), int64(len(body)), PutOptions{ContentType: "text/plain"})
	if err != nil {
		return append(errs, err)
	}
	if info.Size != int64(len(body)) {
		errs = append(errs, errors.New("Put: size mismatch"))
	}
	if info.Checksum == "" {
		errs = append(errs, errors.New("Put: empty checksum (checksums are required)"))
	}

	h, err := s.Head(ctx, key)
	if err != nil {
		errs = append(errs, err)
	} else if h.Key != key {
		errs = append(errs, errors.New("Head: wrong key"))
	}

	rc, gi, err := s.Get(ctx, key, "")
	if err != nil {
		errs = append(errs, err)
	} else {
		got, _ := io.ReadAll(rc)
		_ = rc.Close()
		if !bytes.Equal(got, body) {
			errs = append(errs, errors.New("Get: body mismatch"))
		}
		if gi.Checksum != info.Checksum {
			errs = append(errs, errors.New("Get: checksum mismatch vs Put"))
		}
	}

	// List must actually filter by prefix (return the just-written key).
	if items, err := s.List(ctx, "pf/conformance/"); err != nil {
		errs = append(errs, err)
	} else {
		found := false
		for _, it := range items {
			if it.Key == key {
				found = true
			}
		}
		if !found {
			errs = append(errs, errors.New("List: prefix did not return the written key (real prefix filtering required)"))
		}
	}

	// Capability honesty: a DECLARED capability must work; a false claim fails the suite.
	caps := s.Capabilities()
	if caps.SignedURLs {
		if u, err := s.SignedURL(ctx, key, "GET", time.Minute); err != nil || u == "" {
			errs = append(errs, fmt.Errorf("capability honesty: SignedURLs=true but SignedURL failed/empty: %v", err))
		}
	}
	// NB: versioning/lock/multipart/CMK are intentionally NOT asserted here: a SYNTHESIZED Version (e.g. a
	// content hash, as s3store uses when a bucket has no real version IDs) must not be treated as a version
	// handle, and each of those capabilities needs its own dedicated contract test before it can be trusted.

	if err := s.Delete(ctx, key, ""); err != nil {
		errs = append(errs, err)
	}
	if _, err := s.Head(ctx, key); err == nil {
		errs = append(errs, errors.New("Head after Delete: object still present"))
	}
	return errs
}

// ConformRelationalStore runs the shared RelationalStore conformance basics (reachability + tx rollback).
func ConformRelationalStore(ctx context.Context, s RelationalStore) []error {
	var errs []error
	if err := s.Ping(ctx); err != nil {
		return append(errs, err)
	}
	sentinel := errors.New("pf-conformance-rollback")
	err := s.WithTx(ctx, func(Tx) error { return sentinel })
	if !errors.Is(err, sentinel) {
		errs = append(errs, errors.New("WithTx: error from fn must propagate"))
	}
	return errs
}
