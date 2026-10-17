package residency

import (
	"crypto/ed25519"
	"crypto/rand"
	"path/filepath"
	"testing"
	"time"
)

const cellsDir = "../../../../config/residency-cells"

func testKey(t *testing.T) (ed25519.PublicKey, ed25519.PrivateKey) {
	t.Helper()
	pub, priv, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	return pub, priv
}

func signedCell(t *testing.T, c RegionCell, keyID string, priv ed25519.PrivateKey) RegionCell {
	t.Helper()
	att, err := SignCell(c, keyID, priv)
	if err != nil {
		t.Fatal(err)
	}
	c.Attestation = att
	return c
}

func TestShippedCellsVerifyAgainstShippedKeyring(t *testing.T) {
	cells, err := LoadCells(filepath.Join(cellsDir, "region-cells.json"))
	if err != nil {
		t.Fatal(err)
	}
	keys, err := LoadKeyring(filepath.Join(cellsDir, "attestation-keys.json"))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	if len(cells) < 2 {
		t.Fatalf("want IN + US cells, got %d", len(cells))
	}
	for _, c := range cells {
		if err := VerifyAttestation(c, keys, now); err != nil {
			t.Fatalf("shipped cell %q failed attestation: %v", c.ID, err)
		}
	}
}

func TestVerifyAttestationFailsClosed(t *testing.T) {
	pub, priv := testKey(t)
	keys := Keyring{"k1": pub}
	now := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	base := RegionCell{ID: "x", Region: "US", Capabilities: []string{"pii"}, NotAfter: "2030-01-01T00:00:00Z"}

	ok := signedCell(t, base, "k1", priv)
	if err := VerifyAttestation(ok, keys, now); err != nil {
		t.Fatalf("valid cell rejected: %v", err)
	}
	// tampered capabilities -> digest mismatch
	tampered := ok
	tampered.Capabilities = []string{"pii", "gpu"}
	if err := VerifyAttestation(tampered, keys, now); err == nil {
		t.Fatal("tampered cell must fail")
	}
	// unknown key id
	unknown := ok
	unknown.Attestation.KeyID = "nope"
	if err := VerifyAttestation(unknown, keys, now); err == nil {
		t.Fatal("unknown key must fail closed")
	}
	// expired
	expired := signedCell(t, RegionCell{ID: "e", Region: "US", NotAfter: "2020-01-01T00:00:00Z"}, "k1", priv)
	if err := VerifyAttestation(expired, keys, now); err == nil {
		t.Fatal("expired attestation must fail closed")
	}
}

func TestResolverDeterministicAndFailClosed(t *testing.T) {
	pub, priv := testKey(t)
	keys := Keyring{"k1": pub}
	inCell := signedCell(t, RegionCell{ID: "in-b", Region: "IN", Capabilities: []string{"pii", "in-country"}, NotAfter: "2030-01-01T00:00:00Z"}, "k1", priv)
	inCellA := signedCell(t, RegionCell{ID: "in-a", Region: "IN", Capabilities: []string{"pii", "in-country"}, NotAfter: "2030-01-01T00:00:00Z"}, "k1", priv)
	unattested := RegionCell{ID: "in-c", Region: "IN", Capabilities: []string{"pii", "in-country"}} // no attestation
	r := &RegionResolver{provider: StaticProvider{CellList: []RegionCell{inCell, unattested, inCellA}, Keyring: keys},
		now: func() time.Time { return time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC) }}

	got, err := r.Resolve("IN", []string{"pii"})
	if err != nil || got.ID != "in-a" { // lowest attested id wins; unattested skipped
		t.Fatalf("resolve determinism: %+v err=%v", got, err)
	}
	if _, err := r.Resolve("IN", []string{"gpu"}); err == nil {
		t.Fatal("no compliant cell must fail closed")
	}
	if _, err := r.Resolve("ZZ", nil); err == nil {
		t.Fatal("unknown region must fail closed")
	}
	if _, err := r.Resolve("", nil); err == nil {
		t.Fatal("empty region must fail closed")
	}
}

func TestPolicyEvaluator(t *testing.T) {
	ev := PolicyEvaluator{}
	p := Policy{ID: "p", Version: "1.0", Region: "US", AllowedRegions: []string{"US"}, CrossBorderTransfer: "restricted"}
	if d, _ := ev.Evaluate(TransferRequest{Region: "US", Target: "US"}, p); !d.Allowed {
		t.Fatal("intra-region must be allowed")
	}
	if d, _ := ev.Evaluate(TransferRequest{Region: "US", Target: "IN"}, p); d.Allowed {
		t.Fatal("restricted cross-border must be denied")
	}
	p.CrossBorderTransfer = "allowed"
	if d, _ := ev.Evaluate(TransferRequest{Region: "US", Target: "IN"}, p); !d.Allowed {
		t.Fatal("allowed cross-border must pass")
	}
	p.CrossBorderTransfer = "???"
	if d, _ := ev.Evaluate(TransferRequest{Region: "US", Target: "IN"}, p); d.Allowed {
		t.Fatal("unknown transfer mode must fail closed")
	}
}
