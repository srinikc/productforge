// Command pfmigrate applies versioned schema migrations to the PostgreSQL system of record.
//
// It is an EXPLICIT deploy step (EDP-08 / BI-PF-1300, BI-PF-1309): migrations are never applied on
// application startup. The DSN comes from PF_DB_DSN (or -dsn); migrations come from -dir (default: the
// nearest "migrations" directory walking up from the working directory).
//
// Usage:
//
//	pfmigrate status
//	pfmigrate up
//	pfmigrate down
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"productforge/migrate"
	"productforge/store"
)

func main() {
	fs := flag.NewFlagSet("pfmigrate", flag.ExitOnError)
	dsn := fs.String("dsn", os.Getenv("PF_DB_DSN"), "PostgreSQL DSN (default $PF_DB_DSN)")
	dir := fs.String("dir", "", "migrations directory (default: nearest 'migrations' up from cwd)")
	_ = fs.Parse(os.Args[1:])
	cmd := "status"
	if fs.NArg() > 0 {
		cmd = fs.Arg(0)
	}

	if *dsn == "" {
		fmt.Fprintln(os.Stderr, "PF_DB_DSN is not set (pass -dsn or set the env var)")
		os.Exit(2)
	}
	if *dir == "" {
		d, err := findMigrationsDir()
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		*dir = d
	}

	ctx := context.Background()
	st, err := store.Open(ctx, *dsn)
	if err != nil {
		fmt.Fprintln(os.Stderr, "open:", err)
		os.Exit(1)
	}
	defer st.Close()

	all, err := migrate.LoadDir(*dir)
	if err != nil {
		fmt.Fprintln(os.Stderr, "load:", err)
		os.Exit(1)
	}
	if err := migrate.EnsureTable(ctx, st); err != nil {
		fmt.Fprintln(os.Stderr, "ensure table:", err)
		os.Exit(1)
	}
	applied, err := migrate.Applied(ctx, st)
	if err != nil {
		fmt.Fprintln(os.Stderr, "applied:", err)
		os.Exit(1)
	}

	switch cmd {
	case "status":
		for _, m := range all {
			mark := "pending"
			if applied[m.Version] {
				mark = "applied"
			}
			fmt.Printf("%04d  %-32s %s\n", m.Version, m.Name, mark)
		}
	case "up":
		n, err := migrate.Up(ctx, st, all)
		if err != nil {
			fmt.Fprintln(os.Stderr, "up:", err)
			os.Exit(1)
		}
		fmt.Printf("applied %d migration(s)\n", n)
	case "down":
		if err := migrate.Down(ctx, st, all); err != nil {
			fmt.Fprintln(os.Stderr, "down:", err)
			os.Exit(1)
		}
		fmt.Println("rolled back one migration")
	default:
		fmt.Fprintf(os.Stderr, "unknown command %q (want: up|down|status)\n", cmd)
		os.Exit(2)
	}
}

func findMigrationsDir() (string, error) {
	d, err := os.Getwd()
	if err != nil {
		return "", err
	}
	for {
		cand := filepath.Join(d, "migrations")
		if st, e := os.Stat(cand); e == nil && st.IsDir() {
			return cand, nil
		}
		parent := filepath.Dir(d)
		if parent == d {
			return "", fmt.Errorf("could not locate a 'migrations' directory; pass -dir")
		}
		d = parent
	}
}
