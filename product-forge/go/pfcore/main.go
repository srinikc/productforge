// Command pfcore-host is the PF native Go core host (B1, BI-PF-0394).
// Reads a canonical A1 wire-request from stdin (or a file argument) and writes the
// canonical wire-response to stdout - the same seam as the go/contract host, but for the
// native Go core: new shipped/sensitive features land here and are invoked from the PF
// runtime through this binary.
// Layout mirrors go/contract: single package main dir - library funcs live beside main().
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
		fmt.Fprintln(os.Stderr, "pfcore-host: read error:", err)
		os.Exit(2)
	}
	var req WireRequest
	if err := json.Unmarshal(raw, &req); err != nil {
		fmt.Fprintln(os.Stderr, "pfcore-host: invalid JSON:", err)
		os.Exit(2)
	}
	resp := Handle(req)
	out, err := json.MarshalIndent(resp, "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, "pfcore-host: encode error:", err)
		os.Exit(2)
	}
	fmt.Println(string(out))
}
