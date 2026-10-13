package main

import (
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"testing"
)

func licenseReq(op string, payload map[string]any) WireRequest {
	return WireRequest{Schema: WireRequestSchema, ID: "t", Op: op, ContractName: "license-profile", Payload: payload}
}

func TestLicenseIssueVerifyRoundTripAndTamper(t *testing.T) {
	_, priv, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	lic := map[string]any{
		"schema": "product-forge/license-profile@1", "license_id": "L1", "tier": "starter",
		"tenant": "acme", "seats": float64(5),
	}
	iss := Handle(licenseReq("license.issue", map[string]any{
		"private_key": base64.StdEncoding.EncodeToString(priv.Seed()), "license": lic}))
	if !iss.OK {
		t.Fatalf("issue failed: %s", iss.Error)
	}
	sig, _ := iss.Result["signature"].(string)
	pubB64, _ := iss.Result["public_key"].(string)

	// positive: verify with the issued public key
	v := Handle(licenseReq("license.verify", map[string]any{
		"license": lic, "signature": sig, "public_key": pubB64}))
	if v.Result["valid"] != true {
		t.Fatalf("expected valid=true, got %v (%v)", v.Result, v.Error)
	}

	// tamper: change the tier -> must NOT verify
	tampered := map[string]any{
		"schema": "product-forge/license-profile@1", "license_id": "L1", "tier": "enterprise",
		"tenant": "acme", "seats": float64(5),
	}
	tv := Handle(licenseReq("license.verify", map[string]any{
		"license": tampered, "signature": sig, "public_key": pubB64}))
	if tv.Result["valid"] == true {
		t.Fatalf("tampered license verified (must fail): %v", tv.Result)
	}

	// wrong public key -> must NOT verify
	otherPub, _, _ := ed25519.GenerateKey(rand.Reader)
	wv := Handle(licenseReq("license.verify", map[string]any{
		"license": lic, "signature": sig, "public_key": base64.StdEncoding.EncodeToString(otherPub)}))
	if wv.Result["valid"] == true {
		t.Fatalf("wrong public key verified (must fail): %v", wv.Result)
	}

	// fail-closed: missing fields -> valid=false, never an error
	mv := Handle(licenseReq("license.verify", map[string]any{"license": lic}))
	if mv.Result["valid"] != false {
		t.Fatalf("missing signature must be valid=false, got %v", mv.Result)
	}
}

func TestLicenseVerifyWithRawPublicKey(t *testing.T) {
	pub, priv, _ := ed25519.GenerateKey(rand.Reader)
	lic := map[string]any{"schema": "product-forge/license-profile@1", "tier": "trial"}
	iss := Handle(licenseReq("license.issue", map[string]any{
		"private_key": base64.StdEncoding.EncodeToString(priv.Seed()), "license": lic}))
	sig, _ := iss.Result["signature"].(string)
	v := Handle(licenseReq("license.verify", map[string]any{
		"license": lic, "signature": sig, "public_key": base64.StdEncoding.EncodeToString(pub)}))
	if v.Result["valid"] != true {
		t.Fatalf("expected valid=true, got %v", v.Result)
	}
}
