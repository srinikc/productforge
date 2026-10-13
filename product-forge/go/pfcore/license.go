package main

// license.go (A2, BI-PF-0396): asymmetric license issue/verify in the native Go core.
//
// New shipped/sensitive logic lives here per the LOCKED delivery baseline (BI-PF-0387/0388): the
// product ships the PUBLIC key only and VERIFIES; the vendor PRIVATE key never ships and is passed
// only to the signing tooling (`license.issue`). Stdlib only (crypto/ed25519) so `go build` holds.
//
// Canonicalization: the signed bytes are the deterministic JSON of the license object. Go's
// json.Marshal sorts map keys, so both issue and verify agree on the byte sequence for the same
// object (numbers in the license must be integers to stay stable across the Python<->Go hop).

import (
	"bytes"
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
)

func licenseCanonical(license map[string]any) ([]byte, error) {
	// SetEscapeHTML(false) so the bytes match Python's json.dumps(sort_keys, separators) for ASCII
	// license values (ids/tiers/tenants) - the two sides must sign/verify identical bytes.
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(license); err != nil {
		return nil, err
	}
	return bytes.TrimRight(buf.Bytes(), "\n"), nil
}

// LicenseKeygen returns a fresh Ed25519 keypair (base64 std). Dev/operator setup only.
func LicenseKeygen(req WireRequest) WireResponse {
	pub, priv, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		return response(req, false, "error", nil, "keygen failed: "+err.Error())
	}
	return response(req, true, "ok", map[string]any{
		"private_key": base64.StdEncoding.EncodeToString(priv.Seed()),
		"public_key":  base64.StdEncoding.EncodeToString(pub),
	}, "")
}

// LicenseIssue signs a license body with the vendor Ed25519 private key (base64 32-byte seed).
// Signing-tooling only - never wired into the shipped product path.
func LicenseIssue(req WireRequest) WireResponse {
	privB64, _ := req.Payload["private_key"].(string)
	lic, _ := req.Payload["license"].(map[string]any)
	if privB64 == "" || lic == nil {
		return response(req, false, "error", nil, "private_key and license are required")
	}
	seed, err := base64.StdEncoding.DecodeString(privB64)
	if err != nil || len(seed) != ed25519.SeedSize {
		return response(req, false, "error", nil, "private_key must be base64 of a 32-byte ed25519 seed")
	}
	msg, err := licenseCanonical(lic)
	if err != nil {
		return response(req, false, "error", nil, "license not serializable")
	}
	priv := ed25519.NewKeyFromSeed(seed)
	sig := ed25519.Sign(priv, msg)
	pub := priv.Public().(ed25519.PublicKey)
	return response(req, true, "ok", map[string]any{
		"license":    lic,
		"signature":  base64.StdEncoding.EncodeToString(sig),
		"public_key": base64.StdEncoding.EncodeToString(pub),
	}, "")
}

// LicenseVerify verifies a license body + signature against an Ed25519 public key (base64, 32 bytes).
// Product path: PUBLIC key only; fail-closed (valid=false on any failure; never an error response).
func LicenseVerify(req WireRequest) WireResponse {
	lic, _ := req.Payload["license"].(map[string]any)
	sigB64, _ := req.Payload["signature"].(string)
	pubB64, _ := req.Payload["public_key"].(string)
	if lic == nil || sigB64 == "" || pubB64 == "" {
		return response(req, true, "ok",
			map[string]any{"valid": false, "reason": "license, signature, public_key required"}, "")
	}
	pub, err := base64.StdEncoding.DecodeString(pubB64)
	if err != nil || len(pub) != ed25519.PublicKeySize {
		return response(req, true, "ok",
			map[string]any{"valid": false, "reason": "public_key must be base64 of a 32-byte ed25519 key"}, "")
	}
	sig, err := base64.StdEncoding.DecodeString(sigB64)
	if err != nil {
		return response(req, true, "ok", map[string]any{"valid": false, "reason": "signature must be base64"}, "")
	}
	msg, err := licenseCanonical(lic)
	if err != nil {
		return response(req, true, "ok", map[string]any{"valid": false, "reason": "license not serializable"}, "")
	}
	if !ed25519.Verify(ed25519.PublicKey(pub), msg, sig) {
		return response(req, true, "ok", map[string]any{"valid": false, "reason": "signature does not verify"}, "")
	}
	return response(req, true, "ok", map[string]any{"valid": true, "license": lic}, "")
}
