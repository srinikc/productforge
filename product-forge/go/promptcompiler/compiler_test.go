package promptcompiler

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"
)

func TestRoundTripEncryption(t *testing.T) {
	masterKey := []byte("platform-super-secret-master-key-32")
	salt := bytes.Repeat([]byte{0x42}, SaltLength)

	entries := map[string]string{
		"architect.md": "# Senior Enterprise Architect Persona\nAct as a principal architect.",
		"worker.md":    "# Autonomous Worker Persona\nFollow EOS standard.",
		"system.json":  `{"roles": ["architect", "worker"], "version": "1.0"}`,
	}

	bundle, err := CompileBundle(entries, masterKey, salt)
	if err != nil {
		t.Fatalf("CompileBundle failed: %v", err)
	}

	if len(bundle) <= HeaderLength {
		t.Fatalf("bundle too small: %d bytes", len(bundle))
	}

	decrypted, err := DecryptBundle(bundle, masterKey)
	if err != nil {
		t.Fatalf("DecryptBundle failed: %v", err)
	}

	if len(decrypted) != len(entries) {
		t.Fatalf("expected %d entries, got %d", len(entries), len(decrypted))
	}

	for k, v := range entries {
		if decrypted[k] != v {
			t.Errorf("entry mismatch for %s: got %q, want %q", k, decrypted[k], v)
		}
	}

	// Verify GetPrompt
	prompt, err := GetPrompt(bundle, masterKey, "architect.md")
	if err != nil {
		t.Fatalf("GetPrompt failed: %v", err)
	}
	if prompt != entries["architect.md"] {
		t.Errorf("GetPrompt mismatch: got %q, want %q", prompt, entries["architect.md"])
	}
}

func TestTamperedBundleRejection(t *testing.T) {
	masterKey := []byte("master-key-for-tamper-test-123456")
	entries := map[string]string{
		"secret.md": "Proprietary algorithm instructions",
	}

	bundle, err := CompileBundle(entries, masterKey, nil)
	if err != nil {
		t.Fatalf("CompileBundle failed: %v", err)
	}

	// Tamper with the last byte of ciphertext (which is part of the GCM tag)
	tampered := make([]byte, len(bundle))
	copy(tampered, bundle)
	tampered[len(tampered)-1] ^= 0xFF

	_, err = DecryptBundle(tampered, masterKey)
	if err == nil {
		t.Fatal("expected authentication failure for tampered bundle, but got nil")
	}
	if err != ErrCiphertextAuth {
		t.Errorf("expected ErrCiphertextAuth, got %v", err)
	}
}

func TestInvalidHeader(t *testing.T) {
	badHeader := []byte("XXXX01234567890123456789012345678901234567890123456789")
	_, err := DecryptBundle(badHeader, []byte("some-key"))
	if err != ErrInvalidHeader {
		t.Errorf("expected ErrInvalidHeader, got %v", err)
	}

	shortHeader := []byte("PFA1")
	_, err = DecryptBundle(shortHeader, []byte("some-key"))
	if err != ErrBundleTooShort {
		t.Errorf("expected ErrBundleTooShort, got %v", err)
	}
}

func TestWrongKeyFails(t *testing.T) {
	correctKey := []byte("correct-key-32-bytes-long-123456")
	wrongKey := []byte("wrong-key-32-bytes-long-65432100")

	bundle, err := CompileBundle(map[string]string{"a": "b"}, correctKey, nil)
	if err != nil {
		t.Fatalf("CompileBundle failed: %v", err)
	}

	_, err = DecryptBundle(bundle, wrongKey)
	if err == nil {
		t.Fatal("expected decryption failure with wrong key, got nil")
	}
}

func TestCompileDirectoryToBundle(t *testing.T) {
	tempDir := t.TempDir()
	p1 := filepath.Join(tempDir, "prompts", "test1.md")
	p2 := filepath.Join(tempDir, "prompts", "test2.json")
	if err := os.MkdirAll(filepath.Dir(p1), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(p1, []byte("prompt 1 content"), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(p2, []byte(`{"key": "value"}`), 0644); err != nil {
		t.Fatal(err)
	}

	masterKey := []byte("test-directory-compilation-key32")
	bundle, err := CompileDirectoryToBundle(tempDir, masterKey, nil)
	if err != nil {
		t.Fatalf("CompileDirectoryToBundle failed: %v", err)
	}

	decrypted, err := DecryptBundle(bundle, masterKey)
	if err != nil {
		t.Fatalf("DecryptBundle failed: %v", err)
	}

	if len(decrypted) != 2 {
		t.Fatalf("expected 2 entries, got %d", len(decrypted))
	}
}
