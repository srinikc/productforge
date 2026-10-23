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
	"net/url"
	"strings"
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
}

// S3Store is the S3-compatible ObjectStore adapter.
type S3Store struct {
	client *minio.Client
	bucket string
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
	s := &S3Store{client: cl, bucket: cfg.Bucket}
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
	if mode, until, lerr := retentionFor(opts); lerr != nil {
		return datastore.ObjectInfo{}, lerr
	} else if mode != "" {
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
	return s.client.StatObject(ctx, s.bucket, key, minio.StatObjectOptions{VersionID: version})
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
	return s.client.RemoveObject(ctx, s.bucket, key, minio.RemoveObjectOptions{VersionID: version})
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
	return datastore.Capabilities{SignedURLs: true, ObjectVersioning: true, ObjectLock: true, MultipartUpload: true}
}

// retentionFor maps PutOptions to object-lock headers: retention requires Immutable and a >=1m window.
func retentionFor(opts datastore.PutOptions) (minio.RetentionMode, time.Time, error) {
	if opts.Retention <= 0 {
		return "", time.Time{}, nil
	}
	if !opts.Immutable {
		return "", time.Time{}, errors.New("s3store: retention requires Immutable=true")
	}
	if opts.Retention < time.Minute {
		return "", time.Time{}, errors.New("s3store: retention must be at least 1 minute")
	}
	return minio.Governance, time.Now().Add(opts.Retention), nil
}

// ApplyLifecycle sets object retention/legal hold. COMPLIANCE is irreversible once applied.
func (s *S3Store) ApplyLifecycle(ctx context.Context, key string, policy datastore.LifecyclePolicy) error {
	if strings.TrimSpace(key) == "" {
		return errors.New("s3store: empty key")
	}
	var mode minio.RetentionMode
	switch strings.ToUpper(strings.TrimSpace(policy.Mode)) {
	case "GOVERNANCE":
		mode = minio.Governance
	case "COMPLIANCE":
		mode = minio.Compliance
	case "":
		mode = ""
	default:
		return fmt.Errorf("s3store: unsupported retention mode %q", policy.Mode)
	}
	if mode != "" {
		if policy.RetainUntil.IsZero() || !policy.RetainUntil.After(time.Now()) {
			return errors.New("s3store: RetainUntil must be in the future")
		}
		until := policy.RetainUntil
		if err := s.client.PutObjectRetention(ctx, s.bucket, key, minio.PutObjectRetentionOptions{
			Mode: &mode, RetainUntilDate: &until,
		}); err != nil {
			return fmt.Errorf("s3store: apply retention: %w", err)
		}
	}
	if policy.LegalHold || policy.ReleaseLegalHold {
		status := minio.LegalHoldEnabled
		if policy.ReleaseLegalHold {
			status = minio.LegalHoldDisabled
		}
		if err := s.client.PutObjectLegalHold(ctx, s.bucket, key, minio.PutObjectLegalHoldOptions{
			Status: &status,
		}); err != nil {
			return fmt.Errorf("s3store: apply legal hold: %w", err)
		}
	}
	return nil
}

// ObjectLifecycle returns the effective retention/legal-hold state.
func (s *S3Store) ObjectLifecycle(ctx context.Context, key string) (datastore.LifecycleState, error) {
	var st datastore.LifecycleState
	mode, until, err := s.client.GetObjectRetention(ctx, s.bucket, key, "")
	if err != nil {
		return st, fmt.Errorf("s3store: get retention: %w", err)
	}
	if mode != nil {
		st.Mode = string(*mode)
	}
	if until != nil {
		st.RetainUntil = *until
	}
	hold, err := s.client.GetObjectLegalHold(ctx, s.bucket, key, minio.GetObjectLegalHoldOptions{})
	if err != nil {
		return st, fmt.Errorf("s3store: get legal hold: %w", err)
	}
	if hold != nil && *hold == minio.LegalHoldEnabled {
		st.LegalHold = true
	}
	if ver, err := s.client.GetBucketVersioning(ctx, s.bucket); err == nil {
		st.Versioning = strings.EqualFold(string(ver.Status), "Enabled")
	}
	return st, nil
}
