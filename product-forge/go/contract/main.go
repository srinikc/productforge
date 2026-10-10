// Command contract-host is the Go host side of the Go<->Python wire contract (BI-PF-0393).
//
// It reads ONE canonical wire-request JSON object from a file argument (or stdin), handles it,
// and writes the canonical wire-response JSON to stdout. Zero external dependencies.
//
// Usage:
//
//	contract-host [request.json]   # or: echo '<json>' | contract-host
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
)

func main() {
	var raw []byte
	var err error
	if len(os.Args) > 1 {
		raw, err = os.ReadFile(os.Args[1])
	} else {
		raw, err = io.ReadAll(os.Stdin)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, "contract-host: read error:", err)
		os.Exit(2)
	}
	var req WireRequest
	if err := json.Unmarshal(raw, &req); err != nil {
		fmt.Fprintln(os.Stderr, "contract-host: invalid JSON:", err)
		os.Exit(2)
	}
	resp := Handle(req)
	out, err := json.MarshalIndent(resp, "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, "contract-host: encode error:", err)
		os.Exit(2)
	}
	fmt.Println(string(out))
}
