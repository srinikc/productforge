// Command wg-coordinator is the WorkerGrid coordinator service (Go port of
// workergrid/service.py, BI-PF-0412) - one static binary, no runtime deps.
//
// Usage: wg-coordinator [-host H] [-port P]  (defaults from config.json:
// service_host / service_port; env WORKERGRID_HOME / WORKERGRID_STATE_DIR /
// WORKERGRID_PF_API_URL / WORKERGRID_TOKEN / WORKERGRID_LEASE_SECONDS apply).
package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"workergrid/internal/config"
	"workergrid/internal/httpapi"
	"workergrid/internal/store"
)

func main() {
	host := flag.String("host", "", "bind host (default: config service_host)")
	port := flag.Int("port", 0, "bind port (default: config service_port)")
	flag.Parse()

	cfg := config.Load()
	bindHost := *host
	if bindHost == "" {
		bindHost = cfg.ServiceHost
		if bindHost == "" {
			bindHost = "127.0.0.1"
		}
	}
	bindPort := *port
	if bindPort == 0 {
		bindPort = cfg.ServicePort
		if bindPort == 0 {
			bindPort = 8790
		}
	}

	st, err := store.Open(cfg.StateDir(), cfg.LeaseTTL)
	if err != nil {
		fmt.Fprintf(os.Stderr, "workergrid: open store: %v\n", err)
		os.Exit(1)
	}
	defer st.Close()

	ln, err := net.Listen("tcp", fmt.Sprintf("%s:%d", bindHost, bindPort))
	if err != nil {
		fmt.Fprintf(os.Stderr, "workergrid: listen: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("WorkerGrid service on http://%s:%d (producer=%s)\n",
		bindHost, bindPort, cfg.ProducerBase())

	srv := &http.Server{
		Handler:  httpapi.Handler(st),
		ErrorLog: log.New(io.Discard, "", 0),
	}
	go func() {
		ch := make(chan os.Signal, 1)
		signal.Notify(ch, os.Interrupt, syscall.SIGTERM)
		<-ch
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		_ = srv.Shutdown(ctx)
	}()
	if err := srv.Serve(ln); err != nil && err != http.ErrServerClosed {
		fmt.Fprintf(os.Stderr, "workergrid: serve: %v\n", err)
		os.Exit(1)
	}
}
