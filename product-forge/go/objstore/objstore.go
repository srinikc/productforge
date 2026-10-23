// Package objstore is the local-filesystem datastore.ObjectStore adapter (EDP-13 / BI-PF-1305).
//
// Keys map to files under a confined root; each object has a sidecar metadata file. Writes are atomic
// (temp + fsync + rename) and content-addressed (Version = sha256 checksum). Keys are confined to the root:
// no traversal, no symlink escape. Signed URLs are not supported (declared via Capabilities).
package objstore

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"productforge/datastore"
)

const metaSuffix = ".pfmeta.json"

var (
	// ErrNotSupported is returned for capabilities the local filesystem cannot provide.
	ErrNotSupported = errors.New("objstore: operation not supported by the local filesystem adapter")
	// ErrTooLarge is returned when an object exceeds the configured size limit.
	ErrTooLarge = errors.New("objstore: object exceeds the configured size limit")
	// ErrBadKey is returned for an empty/absolute/traversing/escaping key.
	ErrBadKey = errors.New("objstore: invalid or unsafe key")
)

// LocalStore is the local-filesystem ObjectStore adapter.
type LocalStore struct {
	root    string
	maxSize int64
}

type meta struct {
	Key         string `json:"key"`
	Version     string `json:"version"`
	Checksum    string `json:"checksum"`
	ContentType string `json:"content_type"`
	Size        int64  `json:"size"`
}

// NewLocalStore creates a confined local store rooted at root. maxSize <= 0 means unlimited.
func NewLocalStore(root string, maxSize int64) (*LocalStore, error) {
	if strings.TrimSpace(root) == "" {
		return nil, errors.New("objstore: root is required")
	}
	abs, err := filepath.Abs(root)
	if err != nil {
		return nil, err
	}
	if err := os.MkdirAll(abs, 0o755); err != nil {
		return nil, err
	}
	return &LocalStore{root: abs, maxSize: maxSize}, nil
}

// path resolves a key to a file path confined to the root (traversal is rejected).
func (s *LocalStore) path(key string) (string, error) {
	if strings.TrimSpace(key) == "" || strings.HasPrefix(key, "/") || strings.ContainsAny(key, "\\:") {
		return "", ErrBadKey
	}
	clean := filepath.Clean(key)
	if clean == "." || clean == ".." || strings.HasPrefix(clean, ".."+string(os.PathSeparator)) {
		return "", ErrBadKey
	}
	full := filepath.Join(s.root, clean)
	rel, err := filepath.Rel(s.root, full)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(os.PathSeparator)) {
		return "", ErrBadKey
	}
	return full, nil
}

// ensureDir creates dir and rejects a symlink escape (the resolved dir must stay under root).
func (s *LocalStore) ensureDir(dir string) error {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	real, err := filepath.EvalSymlinks(dir)
	if err != nil {
		return err
	}
	if real != s.root && !strings.HasPrefix(real, s.root+string(os.PathSeparator)) {
		return ErrBadKey
	}
	return nil
}

func (s *LocalStore) init(ctx context.Context) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	default:
		return nil
	}
}

func (s *LocalStore) Put(ctx context.Context, key string, r io.Reader, size int64, opts datastore.PutOptions) (datastore.ObjectInfo, error) {
	if err := s.init(ctx); err != nil {
		return datastore.ObjectInfo{}, err
	}
	full, err := s.path(key)
	if err != nil {
		return datastore.ObjectInfo{}, err
	}
	if opts.ServerSideEncryption != "" {
		return datastore.ObjectInfo{}, fmt.Errorf("objstore: local store cannot honour ServerSideEncryption")
	}
	if opts.Retention > 0 {
		return datastore.ObjectInfo{}, fmt.Errorf("objstore: local store cannot honour object retention: %w", datastore.ErrUnsupported)
	}
	if s.maxSize > 0 && size > s.maxSize {
		return datastore.ObjectInfo{}, ErrTooLarge
	}
	if err := s.ensureDir(filepath.Dir(full)); err != nil {
		return datastore.ObjectInfo{}, err
	}
	tmp, err := os.CreateTemp(filepath.Dir(full), ".tmp-*")
	if err != nil {
		return datastore.ObjectInfo{}, err
	}
	defer func() { _ = os.Remove(tmp.Name()) }()

	h := sha256.New()
	var src io.Reader = r
	if size >= 0 {
		src = io.LimitReader(r, size+1)
	}
	n, err := io.Copy(io.MultiWriter(tmp, h), src)
	if err != nil {
		_ = tmp.Close()
		return datastore.ObjectInfo{}, err
	}
	if s.maxSize > 0 && n > s.maxSize {
		_ = tmp.Close()
		return datastore.ObjectInfo{}, ErrTooLarge
	}
	if size >= 0 && n != size {
		_ = tmp.Close()
		return datastore.ObjectInfo{}, fmt.Errorf("objstore: size mismatch (got %d, want %d)", n, size)
	}
	if err := tmp.Sync(); err != nil {
		_ = tmp.Close()
		return datastore.ObjectInfo{}, err
	}
	if err := tmp.Close(); err != nil {
		return datastore.ObjectInfo{}, err
	}
	sum := hex.EncodeToString(h.Sum(nil))
	if err := os.Rename(tmp.Name(), full); err != nil {
		return datastore.ObjectInfo{}, err
	}
	ct := opts.ContentType
	if ct == "" {
		ct = "application/octet-stream"
	}
	m := meta{Key: key, Version: sum, Checksum: sum, ContentType: ct, Size: n}
	if err := s.writeMeta(full, m); err != nil {
		return datastore.ObjectInfo{}, err
	}
	return info(m), nil
}

func (s *LocalStore) writeMeta(full string, m meta) error {
	b, err := json.Marshal(m)
	if err != nil {
		return err
	}
	tmp, err := os.CreateTemp(filepath.Dir(full), ".meta-*")
	if err != nil {
		return err
	}
	if _, err := tmp.Write(b); err != nil {
		_ = tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	return os.Rename(tmp.Name(), full+metaSuffix)
}

func (s *LocalStore) readMeta(key string) (meta, string, error) {
	full, err := s.path(key)
	if err != nil {
		return meta{}, "", err
	}
	b, err := os.ReadFile(full + metaSuffix)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return meta{}, full, os.ErrNotExist
		}
		return meta{}, full, err
	}
	var m meta
	if err := json.Unmarshal(b, &m); err != nil {
		return meta{}, full, err
	}
	return m, full, nil
}

func (s *LocalStore) Head(ctx context.Context, key string) (datastore.ObjectInfo, error) {
	if err := s.init(ctx); err != nil {
		return datastore.ObjectInfo{}, err
	}
	m, _, err := s.readMeta(key)
	if err != nil {
		return datastore.ObjectInfo{}, err
	}
	return info(m), nil
}

func (s *LocalStore) Get(ctx context.Context, key, version string) (io.ReadCloser, datastore.ObjectInfo, error) {
	if err := s.init(ctx); err != nil {
		return nil, datastore.ObjectInfo{}, err
	}
	m, full, err := s.readMeta(key)
	if err != nil {
		return nil, datastore.ObjectInfo{}, err
	}
	if version != "" && version != m.Version {
		return nil, datastore.ObjectInfo{}, os.ErrNotExist
	}
	f, err := os.Open(full)
	if err != nil {
		return nil, datastore.ObjectInfo{}, err
	}
	return f, info(m), nil
}

func (s *LocalStore) Delete(ctx context.Context, key, version string) error {
	if err := s.init(ctx); err != nil {
		return err
	}
	m, full, err := s.readMeta(key)
	if err != nil {
		return err
	}
	if version != "" && version != m.Version {
		return os.ErrNotExist
	}
	if err := os.Remove(full); err != nil {
		return err
	}
	return os.Remove(full + metaSuffix)
}

func (s *LocalStore) List(ctx context.Context, prefix string) ([]datastore.ObjectInfo, error) {
	if err := s.init(ctx); err != nil {
		return nil, err
	}
	var out []datastore.ObjectInfo
	err := filepath.WalkDir(s.root, func(p string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() || !strings.HasSuffix(p, metaSuffix) {
			return nil
		}
		b, err := os.ReadFile(p)
		if err != nil {
			return err
		}
		var m meta
		if err := json.Unmarshal(b, &m); err != nil {
			return nil
		}
		if strings.HasPrefix(m.Key, prefix) {
			out = append(out, info(m))
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Key < out[j].Key })
	return out, nil
}

func (s *LocalStore) SignedURL(ctx context.Context, key, method string, ttl time.Duration) (string, error) {
	return "", ErrNotSupported
}

func (s *LocalStore) Capabilities() datastore.Capabilities {
	return datastore.Capabilities{}
}

func info(m meta) datastore.ObjectInfo {
	return datastore.ObjectInfo{Key: m.Key, Version: m.Version, Checksum: m.Checksum,
		ContentType: m.ContentType, Size: m.Size}
}

// ApplyLifecycle is unsupported: the local filesystem cannot enforce retention or legal hold.
func (s *LocalStore) ApplyLifecycle(ctx context.Context, key string, policy datastore.LifecyclePolicy) error {
	return fmt.Errorf("objstore: lifecycle/object-lock requires an object-lock capable provider: %w", datastore.ErrUnsupported)
}

// ObjectLifecycle is unsupported on the local adapter.
func (s *LocalStore) ObjectLifecycle(ctx context.Context, key string) (datastore.LifecycleState, error) {
	return datastore.LifecycleState{}, fmt.Errorf("objstore: lifecycle/object-lock requires an object-lock capable provider: %w", datastore.ErrUnsupported)
}
