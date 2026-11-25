// Package s3store is the S3-compatible datastore.ObjectStore adapter (EDP-14 / BI-PF-1306).
//
// It implements the SAME provider-neutral port as the local adapter (go/objstore) over any S3-compatible
// service (AWS S3, MinIO, Ceph) using minio-go. Objects carry a sha256 checksum in user metadata so Put/Get
// agree (S3 ETags are not a content hash for multipart uploads). Presigned URLs back SignedURL.
package s3store

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"log"
	"net/url"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"github.com/minio/minio-go/v7/pkg/encrypt"

	"productforge/datastore"
)

const checksumMeta = "pf-checksum"

// Config configures the S3-compatible adapter.
type Config struct {
	Endpoint  string // host[:port], no scheme
	AccessKey string
	SecretKey string
	Bucket    string
	Region    string
	UseSSL    bool
	Ensure    bool // create the bucket if absent
	// RequireObjectLock makes New fail when the bucket cannot honour object lock (fail at startup, not at
	// retention time). Callers that never lock can leave it false.
	RequireObjectLock bool
}

// S3Store is the S3-compatible ObjectStore adapter.
type S3Store struct {
	client     *minio.Client
	bucket     string
	lockMu     sync.Mutex
	objectLock bool // probed: bucket-level object-lock configuration
	versioned  bool // probed: bucket-level versioning
}

// New creates the adapter and (optionally) ensures the bucket exists.
func New(ctx context.Context, cfg Config) (*S3Store, error) {
	if cfg.Endpoint == "" || cfg.Bucket == "" {
		return nil, errors.New("s3store: endpoint and bucket are required")
	}
	cl, err := minio.New(cfg.Endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(cfg.AccessKey, cfg.SecretKey, ""),
		Secure: cfg.UseSSL,
		Region: cfg.Region,
	})
	if err != nil {
		return nil, err
	}
	s := &S3Store{client: cl, bucket: cfg.Bucket, versioned: true} // probe after an optional bucket create
	if cfg.Ensure {
		ok, err := cl.BucketExists(ctx, cfg.Bucket)
		if err != nil {
			return nil, err
		}
		if !ok {
			if err := cl.MakeBucket(ctx, cfg.Bucket, minio.MakeBucketOptions{Region: cfg.Region}); err != nil {
				return nil, err
			}
		}
	}
	s.probeLock(ctx)
	s.probeVersioning(ctx)
	if cfg.RequireObjectLock {
		s.lockMu.Lock()
		lock := s.objectLock
		s.lockMu.Unlock()
		if !lock {
			return nil, &datastore.UnsupportedError{Provider: "s3", Capability: "object-lock"}
		}
	}
	return s, nil
}

func (s *S3Store) Put(ctx context.Context, key string, r io.Reader, size int64, opts datastore.PutOptions) (datastore.ObjectInfo, error) {
	if strings.TrimSpace(key) == "" {
		return datastore.ObjectInfo{}, errors.New("s3store: empty key")
	}
	// Known-size objects are hashed for the manifest; unknown-size (e.g. pg_dump pipe) stream with a
	// multipart upload so memory stays bounded.
	var sum string
	var body []byte
	if size >= 0 {
		h := sha256.New()
		b, err := io.ReadAll(io.TeeReader(r, h))
		if err != nil {
			return datastore.ObjectInfo{}, err
		}
		if int64(len(b)) != size {
			return datastore.ObjectInfo{}, errors.New("s3store: size mismatch")
		}
		body, sum = b, hex.EncodeToString(h.Sum(nil))
	}
	ct := opts.ContentType
	if ct == "" {
		ct = "application/octet-stream"
	}
	putOpts := minio.PutObjectOptions{ContentType: ct}
	if opts.Retention <= 0 && opts.Immutable {
		s.lockMu.Lock()
		versioned := s.versioned
		s.lockMu.Unlock()
		if !versioned {
			return datastore.ObjectInfo{}, &datastore.UnsupportedError{Provider: "s3", Capability: "immutable-without-versioning"}
		}
	}
	if mode, until, lerr := retentionFor(opts); lerr != nil {
		return datastore.ObjectInfo{}, lerr
	} else if mode != "" {
		s.lockMu.Lock()
		lock := s.objectLock
		s.lockMu.Unlock()
		if !lock {
			return datastore.ObjectInfo{}, fmt.Errorf("s3store: retention requested but the bucket has no object-lock configuration: %w", datastore.ErrUnsupported)
		}
		putOpts.Mode = mode
		putOpts.RetainUntilDate = until
	}
	if size >= 0 {
		putOpts.UserMetadata = map[string]string{checksumMeta: sum}
	}
	if sse := strings.TrimSpace(opts.ServerSideEncryption); sse != "" {
		switch {
		case strings.EqualFold(sse, "AES256"), strings.EqualFold(sse, "SSE-S3"):
			putOpts.ServerSideEncryption = encrypt.NewSSE()
		case strings.HasPrefix(strings.ToLower(sse), "aws:kms"):
			keyID := ""
			if strings.HasPrefix(strings.ToLower(sse), "aws:kms:") {
				keyID = strings.TrimSpace(sse[len("aws:kms:"):])
			}
			if keyID == "" {
				return datastore.ObjectInfo{}, errors.New("s3store: SSE-KMS requires a key id (aws:kms:<key-id>)")
			}
			kms, kerr := encrypt.NewSSEKMS(keyID, nil)
			if kerr != nil {
				return datastore.ObjectInfo{}, fmt.Errorf("s3store: SSE-KMS: %w", kerr)
			}
			putOpts.ServerSideEncryption = kms
		default:
			return datastore.ObjectInfo{}, fmt.Errorf("s3store: unsupported ServerSideEncryption %q", sse)
		}
	}
	var reader io.Reader
	var n int64
	if size >= 0 {
		reader, n = bytes.NewReader(body), int64(len(body))
	} else {
		reader, n = r, -1
		putOpts.PartSize = 16 << 20
	}
	up, err := s.client.PutObject(ctx, s.bucket, key, reader, n, putOpts)
	if err != nil {
		return datastore.ObjectInfo{}, err
	}
	ver := up.VersionID
	if ver == "" {
		ver = sum
	}
	return datastore.ObjectInfo{Key: key, Version: ver, Checksum: sum, ContentType: ct, Size: up.Size}, nil
}

func (s *S3Store) stat(ctx context.Context, key, version string) (minio.ObjectInfo, error) {
	st, err := s.client.StatObject(ctx, s.bucket, key, minio.StatObjectOptions{VersionID: version})
	if err != nil {
		code := minio.ToErrorResponse(err).Code
		if code == "NoSuchKey" || code == "NoSuchVersion" {
			return minio.ObjectInfo{}, os.ErrNotExist
		}
		return minio.ObjectInfo{}, err
	}
	return st, nil
}

func (s *S3Store) Head(ctx context.Context, key string) (datastore.ObjectInfo, error) {
	st, err := s.stat(ctx, key, "")
	if err != nil {
		return datastore.ObjectInfo{}, err
	}
	return s.info(key, st), nil
}

func (s *S3Store) info(key string, st minio.ObjectInfo) datastore.ObjectInfo {
	sum := st.UserMetadata[checksumMeta]
	ver := st.VersionID
	if ver == "" {
		ver = st.ETag
	}
	return datastore.ObjectInfo{Key: key, Version: ver, Checksum: sum, ContentType: st.ContentType, Size: st.Size}
}

func (s *S3Store) Get(ctx context.Context, key, version string) (io.ReadCloser, datastore.ObjectInfo, error) {
	st, err := s.stat(ctx, key, version)
	if err != nil {
		return nil, datastore.ObjectInfo{}, err
	}
	obj, err := s.client.GetObject(ctx, s.bucket, key, minio.GetObjectOptions{VersionID: version})
	if err != nil {
		return nil, datastore.ObjectInfo{}, err
	}
	return obj, s.info(key, st), nil
}

func (s *S3Store) Delete(ctx context.Context, key, version string) error {
	err := s.client.RemoveObject(ctx, s.bucket, key, minio.RemoveObjectOptions{VersionID: version})
	if err != nil && minio.ToErrorResponse(err).Code == "NoSuchKey" {
		return os.ErrNotExist
	}
	return err
}

func (s *S3Store) List(ctx context.Context, prefix string) ([]datastore.ObjectInfo, error) {
	var out []datastore.ObjectInfo
	for o := range s.client.ListObjects(ctx, s.bucket, minio.ListObjectsOptions{Prefix: prefix, Recursive: true}) {
		if o.Err != nil {
			return nil, o.Err
		}
		out = append(out, s.info(o.Key, o))
	}
	return out, nil
}

// ListPage streams one page of objects after marker (StartAfter) so scans stay memory-bounded.
func (s *S3Store) ListPage(ctx context.Context, prefix, marker string, limit int) ([]datastore.ObjectInfo, string, error) {
	var out []datastore.ObjectInfo
	for o := range s.client.ListObjects(ctx, s.bucket, minio.ListObjectsOptions{
		Prefix: prefix, Recursive: true, StartAfter: marker,
	}) {
		if o.Err != nil {
			return nil, "", o.Err
		}
		out = append(out, s.info(o.Key, o))
		if limit > 0 && len(out) >= limit {
			return out, o.Key, nil
		}
	}
	return out, "", nil
}

func (s *S3Store) SignedURL(ctx context.Context, key, method string, ttl time.Duration) (string, error) {
	if ttl <= 0 {
		ttl = 15 * time.Minute
	}
	var u *url.URL
	var err error
	switch strings.ToUpper(method) {
	case "PUT":
		u, err = s.client.PresignedPutObject(ctx, s.bucket, key, ttl)
	default:
		u, err = s.client.PresignedGetObject(ctx, s.bucket, key, ttl, nil)
	}
	if err != nil {
		return "", err
	}
	return u.String(), nil
}

func (s *S3Store) Capabilities() datastore.Capabilities {
	s.lockMu.Lock()
	lock := s.objectLock
	s.lockMu.Unlock()
	s.lockMu.Lock()
	versioned := s.versioned
	s.lockMu.Unlock()
	return datastore.Capabilities{SignedURLs: true, ObjectVersioning: versioned, ObjectLock: lock, MultipartUpload: true}
}

// retentionFor maps PutOptions to object-lock headers. GOVERNANCE is the default; COMPLIANCE must be named
// explicitly (it is irreversible). Retention always requires Immutable.
func retentionFor(opts datastore.PutOptions) (minio.RetentionMode, time.Time, error) {
	if opts.Retention <= 0 {
		if strings.TrimSpace(opts.RetentionMode) != "" {
			return "", time.Time{}, fmt.Errorf("%w: RetentionMode requires Retention", datastore.ErrInvalidPolicy)
		}
		return "", time.Time{}, nil
	}
	if !opts.Immutable {
		return "", time.Time{}, fmt.Errorf("%w: retention requires Immutable=true", datastore.ErrInvalidPolicy)
	}
	if opts.Retention < time.Minute {
		return "", time.Time{}, fmt.Errorf("%w: retention must be at least 1 minute", datastore.ErrInvalidPolicy)
	}
	mode := strings.ToUpper(strings.TrimSpace(opts.RetentionMode))
	switch mode {
	case "", "GOVERNANCE":
		return minio.Governance, time.Now().Add(opts.Retention), nil
	case "COMPLIANCE":
		if !opts.ComplianceOptIn {
			return "", time.Time{}, fmt.Errorf("%w: COMPLIANCE requires ComplianceOptIn=true", datastore.ErrInvalidPolicy)
		}
		return minio.Compliance, time.Now().Add(opts.Retention), nil
	default:
		return "", time.Time{}, fmt.Errorf("%w: unknown retention mode %q", datastore.ErrInvalidPolicy, opts.RetentionMode)
	}
}

// ApplyLifecycle sets object retention/legal hold. All arguments are validated BEFORE any mutation;
// COMPLIANCE requires an explicit opt-in and is irreversible. A failure after retention is reported as a
// typed PartialApplyError so callers know the object is already locked.
func (s *S3Store) ApplyLifecycle(ctx context.Context, key, version string, policy datastore.LifecyclePolicy) error {
	if strings.TrimSpace(key) == "" {
		return fmt.Errorf("%w: empty key", datastore.ErrInvalidPolicy)
	}
	if policy.LegalHold && policy.ReleaseLegalHold {
		return fmt.Errorf("%w: LegalHold and ReleaseLegalHold are mutually exclusive", datastore.ErrInvalidPolicy)
	}
	if strings.TrimSpace(policy.Mode) == "" && !policy.RetainUntil.IsZero() {
		return fmt.Errorf("%w: RetainUntil requires a retention mode", datastore.ErrInvalidPolicy)
	}
	var mode minio.RetentionMode
	switch strings.ToUpper(strings.TrimSpace(policy.Mode)) {
	case "GOVERNANCE":
		mode = minio.Governance
	case "COMPLIANCE":
		if !policy.ComplianceOptIn {
			return fmt.Errorf("%w: COMPLIANCE requires ComplianceOptIn=true (irreversible)", datastore.ErrInvalidPolicy)
		}
		mode = minio.Compliance
	case "":
	default:
		return fmt.Errorf("%w: unsupported retention mode %q", datastore.ErrInvalidPolicy, policy.Mode)
	}
	if mode != "" && (policy.RetainUntil.IsZero() || !policy.RetainUntil.After(time.Now())) {
		return fmt.Errorf("%w: RetainUntil must be in the future", datastore.ErrInvalidPolicy)
	}

	s.lockMu.Lock()
	lock := s.objectLock
	s.lockMu.Unlock()
	if !lock {
		s.probeLock(ctx)
		s.lockMu.Lock()
		lock = s.objectLock
		s.lockMu.Unlock()
		if !lock {
			return &datastore.UnsupportedError{Provider: "s3", Capability: "object-lock"}
		}
	}
	if mode != "" {
		until := policy.RetainUntil
		if err := s.client.PutObjectRetention(ctx, s.bucket, key, minio.PutObjectRetentionOptions{
			Mode: &mode, RetainUntilDate: &until, VersionID: version,
		}); err != nil {
			return fmt.Errorf("s3store: apply retention: %w", err)
		}
	}
	if policy.LegalHold || policy.ReleaseLegalHold {
		status := legalHoldStatus(policy)
		if err := s.client.PutObjectLegalHold(ctx, s.bucket, key, minio.PutObjectLegalHoldOptions{
			Status: &status, VersionID: version,
		}); err != nil {
			if mode != "" {
				return &datastore.PartialApplyError{Applied: "retention", Err: fmt.Errorf("legal hold: %w", err)}
			}
			return fmt.Errorf("s3store: apply legal hold: %w", err)
		}
	}
	return nil
}

// legalHoldStatus maps the policy flags to the provider status.
func legalHoldStatus(policy datastore.LifecyclePolicy) minio.LegalHoldStatus {
	if policy.ReleaseLegalHold {
		return minio.LegalHoldDisabled
	}
	return minio.LegalHoldEnabled
}

// ObjectLifecycle returns the effective retention/legal-hold state.
func (s *S3Store) ObjectLifecycle(ctx context.Context, key, version string) (datastore.LifecycleState, error) {
	var st datastore.LifecycleState
	s.lockMu.Lock()
	lock := s.objectLock
	s.lockMu.Unlock()
	if !lock {
		return st, &datastore.UnsupportedError{Provider: "s3", Capability: "object-lock"}
	}
	mode, until, err := s.client.GetObjectRetention(ctx, s.bucket, key, version)
	if err != nil {
		return st, fmt.Errorf("s3store: get retention: %w", err)
	}
	if mode != nil {
		st.Mode = string(*mode)
	}
	if until != nil {
		st.RetainUntil = *until
	}
	hold, err := s.client.GetObjectLegalHold(ctx, s.bucket, key, minio.GetObjectLegalHoldOptions{VersionID: version})
	if err != nil {
		return st, fmt.Errorf("s3store: get legal hold: %w", err)
	}
	if hold != nil && *hold == minio.LegalHoldEnabled {
		st.LegalHold = true
	}
	s.lockMu.Lock()
	st.Versioning = s.versioned
	s.lockMu.Unlock()
	return st, nil
}

func (s *S3Store) probeLock(ctx context.Context) {
	if _, _, _, _, err := s.client.GetObjectLockConfig(ctx, s.bucket); err != nil {
		log.Printf("s3store: object-lock probe failed for bucket %q: %v", s.bucket, err)
		return
	}
	s.lockMu.Lock()
	s.objectLock = true
	s.lockMu.Unlock()
}

func (s *S3Store) probeVersioning(ctx context.Context) {
	ver, err := s.client.GetBucketVersioning(ctx, s.bucket)
	s.lockMu.Lock()
	defer s.lockMu.Unlock()
	if err != nil {
		s.versioned = false
		log.Printf("s3store: versioning probe failed for bucket %q: %v", s.bucket, err)
		return
	}
	s.versioned = strings.EqualFold(string(ver.Status), "Enabled")
}

// Provider identifies the adapter in typed capability errors.
func (s *S3Store) Provider() string { return "s3" }
