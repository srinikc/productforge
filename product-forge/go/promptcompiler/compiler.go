// Package promptcompiler provides secure compilation, AES-256-GCM encryption,
// and in-memory decryption for proprietary agent prompt and persona assets.
package promptcompiler

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

var (
	// MagicHeader represents the 4-byte signature for Product Forge Asset bundles.
	MagicHeader = []byte{'P', 'F', 'A', '1'}
	// BundleVersion represents the bundle schema version (v1).
	BundleVersion uint16 = 1

	ErrInvalidHeader  = errors.New("promptcompiler: invalid bundle magic header")
	ErrUnsupportedVer = errors.New("promptcompiler: unsupported bundle version")
	ErrBundleTooShort = errors.New("promptcompiler: bundle data shorter than minimum header size")
	ErrCiphertextAuth = errors.New("promptcompiler: authentication failed or corrupted ciphertext")
	ErrEmptyMasterKey = errors.New("promptcompiler: master key cannot be empty")
)

const (
	SaltLength   = 16
	NonceLength  = 12
	KeyLength    = 32                               // 256 bits for AES-256
	HeaderLength = 4 + 2 + SaltLength + NonceLength // 34 bytes
)

// DeriveKey derives a 32-byte AES-256 key from a master key and salt using HKDF-SHA256 (RFC 5869).
func DeriveKey(masterKey, salt, info []byte) ([]byte, error) {
	if len(masterKey) == 0 {
		return nil, ErrEmptyMasterKey
	}
	if len(salt) == 0 {
		salt = make([]byte, sha256.Size)
	}

	// HKDF-Extract: PRK = HMAC-Hash(salt, IKM)
	extractor := hmac.New(sha256.New, salt)
	extractor.Write(masterKey)
	prk := extractor.Sum(nil)

	// HKDF-Expand: OKM = HMAC-Hash(PRK, info || 0x01)
	expander := hmac.New(sha256.New, prk)
	expander.Write(info)
	expander.Write([]byte{0x01})
	okm := expander.Sum(nil)

	if len(okm) < KeyLength {
		return nil, fmt.Errorf("promptcompiler: derived key length insufficient: %d", len(okm))
	}
	return okm[:KeyLength], nil
}

// CompileBundle serializes entries to JSON and encrypts them with AES-256-GCM.
func CompileBundle(entries map[string]string, masterKey, salt []byte) ([]byte, error) {
	if len(masterKey) == 0 {
		return nil, ErrEmptyMasterKey
	}

	if len(salt) == 0 {
		salt = make([]byte, SaltLength)
		if _, err := io.ReadFull(rand.Reader, salt); err != nil {
			return nil, fmt.Errorf("promptcompiler: failed generating random salt: %w", err)
		}
	} else if len(salt) != SaltLength {
		return nil, fmt.Errorf("promptcompiler: salt must be exactly %d bytes, got %d", SaltLength, len(salt))
	}

	payload, err := json.Marshal(entries)
	if err != nil {
		return nil, fmt.Errorf("promptcompiler: failed marshaling prompt entries: %w", err)
	}

	key, err := DeriveKey(masterKey, salt, []byte("PFA1-AES256GCM"))
	if err != nil {
		return nil, err
	}

	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, fmt.Errorf("promptcompiler: cipher creation failed: %w", err)
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, fmt.Errorf("promptcompiler: GCM creation failed: %w", err)
	}

	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return nil, fmt.Errorf("promptcompiler: failed generating random nonce: %w", err)
	}

	// Additional Authenticated Data includes magic header and version
	aad := append(MagicHeader, byte(BundleVersion>>8), byte(BundleVersion&0xFF))
	ciphertext := gcm.Seal(nil, nonce, payload, aad)

	// Layout: [Magic(4)][Version(2)][Salt(16)][Nonce(12)][Ciphertext(with GCM tag)]
	var buf bytes.Buffer
	buf.Write(MagicHeader)
	var verBytes [2]byte
	binary.BigEndian.PutUint16(verBytes[:], BundleVersion)
	buf.Write(verBytes[:])
	buf.Write(salt)
	buf.Write(nonce)
	buf.Write(ciphertext)

	return buf.Bytes(), nil
}

// VerifyBundleHeader validates the header and unpacks salt, nonce, and ciphertext.
func VerifyBundleHeader(data []byte) (salt, nonce, ciphertext []byte, err error) {
	if len(data) < HeaderLength+16 { // at least header + 16-byte GCM tag
		return nil, nil, nil, ErrBundleTooShort
	}

	if !bytes.Equal(data[:4], MagicHeader) {
		return nil, nil, nil, ErrInvalidHeader
	}

	version := binary.BigEndian.Uint16(data[4:6])
	if version != BundleVersion {
		return nil, nil, nil, fmt.Errorf("%w: got %d, expected %d", ErrUnsupportedVer, version, BundleVersion)
	}

	salt = data[6 : 6+SaltLength]
	nonce = data[6+SaltLength : HeaderLength]
	ciphertext = data[HeaderLength:]
	return salt, nonce, ciphertext, nil
}

// CompileDirectoryToBundle reads all prompt and persona files from a directory and compiles them into a bundle.
func CompileDirectoryToBundle(dirPath string, masterKey, salt []byte) ([]byte, error) {
	entries := make(map[string]string)

	err := filepath.Walk(dirPath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() {
			return nil
		}
		ext := filepath.Ext(path)
		if ext == ".md" || ext == ".json" || ext == ".txt" {
			rel, err := filepath.Rel(dirPath, path)
			if err != nil {
				return err
			}
			content, err := os.ReadFile(path)
			if err != nil {
				return err
			}
			// Normalize to forward slashes for cross-platform portability
			cleanKey := filepath.ToSlash(rel)
			entries[cleanKey] = string(content)
		}
		return nil
	})

	if err != nil {
		return nil, fmt.Errorf("promptcompiler: failed scanning directory %s: %w", dirPath, err)
	}

	return CompileBundle(entries, masterKey, salt)
}
