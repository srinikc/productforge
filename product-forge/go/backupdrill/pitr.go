package backupdrill

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
)

// PITRReport is the readiness of point-in-time recovery on a cluster.
type PITRReport struct {
	WalLevel        string        `json:"wal_level"`
	ArchiveMode     string        `json:"archive_mode"`
	ArchiveCommand  string        `json:"archive_command"`
	LastArchivedAgo time.Duration `json:"last_archived_ago"`
	FailedArchives  int64         `json:"failed_archives"`
	OK              bool          `json:"ok"`
	Problems        []string      `json:"problems"`
}

func pitrProblems(walLevel, archiveMode, archiveCommand string) []string {
	var p []string
	if walLevel != "replica" && walLevel != "logical" {
		p = append(p, "wal_level must be replica or logical")
	}
	if archiveMode != "on" && archiveMode != "always" {
		p = append(p, "archive_mode must be on (or always)")
	}
	if archiveCommand == "" || archiveCommand == "(disabled)" {
		p = append(p, "archive_command is empty/disabled")
	}
	return p
}

// CheckPITR reads pg_settings + pg_stat_archiver.
func CheckPITR(ctx context.Context, conn *pgx.Conn) (PITRReport, error) {
	var r PITRReport
	rows, err := conn.Query(ctx, `SELECT name, setting FROM pg_settings
		WHERE name IN ('wal_level','archive_mode','archive_command')`)
	if err != nil {
		return r, err
	}
	for rows.Next() {
		var name, val string
		if err := rows.Scan(&name, &val); err != nil {
			rows.Close()
			return r, err
		}
		switch name {
		case "wal_level":
			r.WalLevel = val
		case "archive_mode":
			r.ArchiveMode = val
		case "archive_command":
			r.ArchiveCommand = val
		}
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return r, err
	}
	var last *time.Time
	var failed *int64
	_ = conn.QueryRow(ctx, `SELECT last_archived_time, failed_count FROM pg_stat_archiver`).Scan(&last, &failed)
	if failed != nil {
		r.FailedArchives = *failed
	}
	if last != nil {
		r.LastArchivedAgo = time.Since(*last)
	}
	r.Problems = pitrProblems(r.WalLevel, r.ArchiveMode, r.ArchiveCommand)
	if r.FailedArchives > 0 {
		r.Problems = append(r.Problems, fmt.Sprintf("%d failed archive(s)", r.FailedArchives))
	}
	if last == nil {
		r.Problems = append(r.Problems, "no WAL segment archived yet")
	}
	r.OK = len(r.Problems) == 0
	return r, nil
}
