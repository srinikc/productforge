package promptcompiler

import (
	"crypto/aes"
	"crypto/cipher"
	"encoding/json"
	"fmt"
)

// DecryptBundle unpacks and decrypts an encrypted asset bundle entirely in-memory.
// It never writes temporary files to disk, preventing plaintext disk leakage.
func DecryptBundle(bundleData, masterKey []byte) (map[string]string, error) {
	salt, nonce, ciphertext, err := VerifyBundleHeader(bundleData)
	if err != nil {
		return nil, err
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

	aad := append(MagicHeader, byte(BundleVersion>>8), byte(BundleVersion&0xFF))
	plaintext, err := gcm.Open(nil, nonce, ciphertext, aad)
	if err != nil {
		return nil, ErrCiphertextAuth
	}

	entries := make(map[string]string)
	if err := json.Unmarshal(plaintext, &entries); err != nil {
		return nil, fmt.Errorf("promptcompiler: failed unmarshaling payload: %w", err)
	}

	return entries, nil
}

// GetPrompt retrieves a single prompt by its key from the encrypted bundle in-memory.
func GetPrompt(bundleData, masterKey []byte, promptKey string) (string, error) {
	entries, err := DecryptBundle(bundleData, masterKey)
	if err != nil {
		return "", err
	}
	content, ok := entries[promptKey]
	if !ok {
		return "", fmt.Errorf("promptcompiler: prompt %q not found in bundle", promptKey)
	}
	return content, nil
}
