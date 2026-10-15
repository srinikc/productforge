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
	"io"
	"net/url"
	"strings"
	"time"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"

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
	h := sha256.New()
	body, err := io.ReadAll(io.TeeReader(r, h))
	if err != nil {
		return datastore.ObjectInfo{}, err
	}
	if size >= 0 && int64(len(body)) != size {
		return datastore.ObjectInfo{}, errors.New("s3store: size mismatch")
	}
	sum := hex.EncodeToString(h.Sum(nil))
	ct := opts.ContentType
	if ct == "" {
		ct = "application/octet-stream"
	}
	up, err := s.client.PutObject(ctx, s.bucket, key, bytes.NewReader(body), int64(len(body)),
		minio.PutObjectOptions{ContentType: ct, UserMetadata: map[string]string{checksumMeta: sum}})
	if err != nil {
		return datastore.ObjectInfo{}, err
	}
	ver := up.VersionID
	if ver == "" {
		ver = sum
	}
	return datastore.ObjectInfo{Key: key, Version: ver, Checksum: sum, ContentType: ct, Size: int64(len(body))}, nil
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
	return datastore.Capabilities{SignedURLs: true, ObjectVersioning: true, MultipartUpload: true}
}
