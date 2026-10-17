package residency

import (
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"sort"
	"strings"
	"time"
)

// RegionCell is a deployable, region-scoped residency cell together with its capability attestation.
// The cell capabilities are what a tenant's data/services require (e.g. "pii", "kms", "in-country").
type RegionCell struct {
	ID           string      `json:"id"`
	Region       string      `json:"region"`
	Capabilities []string    `json:"capabilities"`
	NotAfter     string      `json:"not_after"` // RFC3339 attestation expiry; fail-closed once passed
	Attestation  Attestation `json:"attestation"`
}

// Attestation binds a cell to its capabilities: the signature covers the canonical payload, and CellDigest is
// the sha256 of that same payload so a tampered capability set cannot be swapped under the signature.
type Attestation struct {
	KeyID      string `json:"key_id"`
	CellDigest string `json:"cell_digest"` // hex(sha256(canonical payload))
	Sig        string `json:"sig"`         // base64(std) ed25519 signature over the canonical payload
}

// Keyring maps key_id -> trusted Ed25519 attestation public key.
type Keyring map[string]ed25519.PublicKey

// cellPayload is the canonical, signed form of a cell (fixed field order; capabilities sorted).
type cellPayload struct {
	ID           string   `json:"id"`
	Region       string   `json:"region"`
	Capabilities []string `json:"capabilities"`
	NotAfter     string   `json:"not_after"`
}

func canonicalCell(c RegionCell) ([]byte, error) {
	caps := append([]string(nil), c.Capabilities...)
	sort.Strings(caps)
	return json.Marshal(cellPayload{
		ID: c.ID, Region: strings.ToUpper(strings.TrimSpace(c.Region)), Capabilities: caps, NotAfter: c.NotAfter,
	})
}

func cellDigest(canonical []byte) string {
	s := sha256.Sum256(canonical)
	return hex.EncodeToString(s[:])
}

// VerifyAttestation verifies a cell's attestation against the keyring at time now (fail-closed on any of:
// unknown key, digest mismatch, bad/invalid signature, expired not_after).
func VerifyAttestation(c RegionCell, keys Keyring, now time.Time) error {
	if strings.TrimSpace(c.ID) == "" || strings.TrimSpace(c.Region) == "" {
		return errors.New("residency: cell id and region are required")
	}
	pk, ok := keys[strings.TrimSpace(c.Attestation.KeyID)]
	if !ok {
		return fmt.Errorf("residency: cell %q: unknown attestation key %q", c.ID, c.Attestation.KeyID)
	}
	canonical, err := canonicalCell(c)
	if err != nil {
		return err
	}
	if cellDigest(canonical) != c.Attestation.CellDigest {
		return fmt.Errorf("residency: cell %q: attestation digest mismatch (tampered)", c.ID)
	}
	sig, err := base64.StdEncoding.DecodeString(c.Attestation.Sig)
	if err != nil || len(sig) != ed25519.SignatureSize {
		return fmt.Errorf("residency: cell %q: malformed attestation signature", c.ID)
	}
	if !ed25519.Verify(pk, canonical, sig) {
		return fmt.Errorf("residency: cell %q: attestation signature invalid", c.ID)
	}
	if strings.TrimSpace(c.NotAfter) != "" {
		exp, err := time.Parse(time.RFC3339, c.NotAfter)
		if err != nil {
			return fmt.Errorf("residency: cell %q: bad not_after: %w", c.ID, err)
		}
		if !now.Before(exp) {
			return fmt.Errorf("residency: cell %q: attestation expired at %s", c.ID, c.NotAfter)
		}
	}
	return nil
}

// SignCell signs a cell payload with an Ed25519 private key, returning the filled Attestation. Signing tooling
// only (the dev/ops attest command); never on the request path.
func SignCell(c RegionCell, keyID string, priv ed25519.PrivateKey) (Attestation, error) {
	canonical, err := canonicalCell(c)
	if err != nil {
		return Attestation{}, err
	}
	return Attestation{
		KeyID:      keyID,
		CellDigest: cellDigest(canonical),
		Sig:        base64.StdEncoding.EncodeToString(ed25519.Sign(priv, canonical)),
	}, nil
}

// LoadKeyring loads trusted attestation public keys from {"keys": {"<id>": {"public_key": "<b64>"}}}.
func LoadKeyring(path string) (Keyring, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("residency: read keyring %q: %w", path, err)
	}
	var doc struct {
		Keys map[string]struct {
			PublicKey string `json:"public_key"`
		} `json:"keys"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		return nil, fmt.Errorf("residency: parse keyring %q: %w", path, err)
	}
	if len(doc.Keys) == 0 {
		return nil, fmt.Errorf("residency: keyring %q has no keys", path)
	}
	out := Keyring{}
	for id, k := range doc.Keys {
		pk, err := base64.StdEncoding.DecodeString(k.PublicKey)
		if err != nil || len(pk) != ed25519.PublicKeySize {
			return nil, fmt.Errorf("residency: keyring %q: key %q is not a base64 32-byte ed25519 public key", path, id)
		}
		out[id] = ed25519.PublicKey(pk)
	}
	return out, nil
}

// LoadCells loads the region-cell registry from {"cells": [ ... ]}.
func LoadCells(path string) ([]RegionCell, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("residency: read cells %q: %w", path, err)
	}
	var doc struct {
		Cells []RegionCell `json:"cells"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		return nil, fmt.Errorf("residency: parse cells %q: %w", path, err)
	}
	if len(doc.Cells) == 0 {
		return nil, fmt.Errorf("residency: cells %q has no cells", path)
	}
	return doc.Cells, nil
}
