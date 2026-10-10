// Command wg-agent is the WorkerGrid worker agent (BI-PF-0413): it claims
// eligible work from the coordinator, executes it in an isolated git worktree
// via a configured runtime command, renews its lease, and writes execution
// status back to the producer. One process = one execution slot.
//
// Usage: wg-agent [-runtime R] [-worker-id W] [-scope S] [-project P] [-epic E]
//
//	[-service URL] [-once]
//
// Defaults: runtime "command", scope "product_forge", service = config
// service_url/host:port. Env: WORKERGRID_HOME / WORKERGRID_STATE_DIR /
// WORKERGRID_PF_API_URL / WORKERGRID_TOKEN / WORKERGRID_LEASE_SECONDS apply.
package main

import (
	"flag"
	"fmt"
	"os"

	"workergrid/internal/agent"
)

func main() {
	runtimeName := flag.String("runtime", "", "runtime whose agent.runtimes.<name>.command to run (default: command)")
	workerID := flag.String("worker-id", "", "worker id to register (default: generated)")
	scope := flag.String("scope", "product_forge", "producer scope to claim work from")
	project := flag.String("project", "", "producer project (optional)")
	epic := flag.String("epic", "", "restrict claims to this epic's children (optional; BI-PF-1222)")
	service := flag.String("service", "", "coordinator base URL (default: config service_url/host:port)")
	once := flag.Bool("once", false, "claim+run at most one item, then exit (tests/one-shots)")
	flag.Parse()

	if err := agent.Run(agent.Options{
		WorkerID: *workerID,
		Runtime:  *runtimeName,
		Scope:    *scope,
		Project:  *project,
		Epic:     *epic,
		Service:  *service,
		Once:     *once,
	}); err != nil {
		fmt.Fprintf(os.Stderr, "wg-agent: %v\n", err)
		os.Exit(1)
	}
}
