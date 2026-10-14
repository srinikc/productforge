package datastore

import (
	"bytes"
	"context"
	"errors"
	"io"
)

// ConformObjectStore runs the shared ObjectStore conformance suite against an adapter. It returns a slice
// of failures (empty == conformant). Adapters (local FS, S3-compatible, ...) MUST pass this suite; it is the
// contract that lets domain code swap providers without change (ADR-0006).
func ConformObjectStore(ctx context.Context, s ObjectStore) []error {
	var errs []error
	key := "pf/conformance/probe"
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

	if _, err := s.List(ctx, "pf/conformance/"); err != nil {
		errs = append(errs, err)
	}

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
