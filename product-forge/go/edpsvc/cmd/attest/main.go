// Command attest is the EDP-11 region-cell ATTESTATION signing tool (dev/ops only; never on the request path).
//
//	attest keygen <private-key-out>                       # write a base64 ed25519 seed; print the public key
//	attest sign <cells.json> <private-key> <key_id> <out-cells.json> <out-keys.json>
//
// The <cells.json> template holds {"cells":[{id,region,capabilities,not_after}, ...]} (no attestation); sign
// fills each attestation and writes the signed registry + the public keyring. Mirrors go/pfcore license
// issue/verify (stdlib ed25519, canonical JSON).
package main

import (
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"

	"productforge/edpsvc/internal/residency"
)

func main() {
	if len(os.Args) < 2 {
		usage()
	}
	switch os.Args[1] {
	case "keygen":
		keygen(os.Args[2:])
	case "sign":
		sign(os.Args[2:])
	default:
		usage()
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage:\n  attest keygen <private-key-out>\n  attest sign <cells.json> <private-key> <key_id> <out-cells.json> <out-keys.json>")
	os.Exit(2)
}

func keygen(args []string) {
	if len(args) != 1 {
		usage()
	}
	pub, priv, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		fail(err)
	}
	if err := os.WriteFile(args[0], []byte(base64.StdEncoding.EncodeToString(priv.Seed())), 0o600); err != nil {
		fail(err)
	}
	fmt.Println(base64.StdEncoding.EncodeToString(pub))
}

func sign(args []string) {
	if len(args) != 5 {
		usage()
	}
	tmplPath, privPath, keyID, outCells, outKeys := args[0], args[1], args[2], args[3], args[4]
	raw, err := os.ReadFile(tmplPath)
	if err != nil {
		fail(err)
	}
	var doc struct {
		Cells []residency.RegionCell `json:"cells"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		fail(err)
	}
	seed, err := os.ReadFile(privPath)
	if err != nil {
		fail(err)
	}
	rawSeed, err := base64.StdEncoding.DecodeString(string(seed))
	if err != nil || len(rawSeed) != ed25519.SeedSize {
		fail(fmt.Errorf("private key must be base64 of a 32-byte ed25519 seed"))
	}
	priv := ed25519.NewKeyFromSeed(rawSeed)
	pub := priv.Public().(ed25519.PublicKey)

	for i := range doc.Cells {
		att, err := residency.SignCell(doc.Cells[i], keyID, priv)
		if err != nil {
			fail(err)
		}
		doc.Cells[i].Attestation = att
	}
	writeJSON(outCells, doc)
	writeJSON(outKeys, map[string]any{
		"keys": map[string]any{keyID: map[string]any{
			"public_key": base64.StdEncoding.EncodeToString(pub),
			"note":       "EDP-11 region-cell attestation key (dev); rotate via a new key_id",
		}},
	})
	fmt.Printf("signed %d cell(s) with key %q\n", len(doc.Cells), keyID)
}

func writeJSON(path string, v any) {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		fail(err)
	}
	if err := os.WriteFile(path, append(b, '\n'), 0o644); err != nil {
		fail(err)
	}
}

func fail(err error) {
	fmt.Fprintln(os.Stderr, "attest:", err)
	os.Exit(1)
}
