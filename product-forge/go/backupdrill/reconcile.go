package backupdrill

import (
	"context"
	"fmt"
	"sort"

	"github.com/jackc/pgx/v5"
	"productforge/datastore"
)

// ObjectRow is an object reference held by the database.
type ObjectRow struct {
	Table    string
	Ref      string
	Checksum string
}

type Drift struct {
	Missing  []string `json:"missing"`  // metadata rows whose object is absent
	Orphaned []string `json:"orphaned"` // objects with no metadata row
}

func (d Drift) Clean() bool { return len(d.Missing)+len(d.Orphaned) == 0 }

// Classify compares metadata refs with the object listing (prefix scoped).
func Classify(rows map[string]ObjectRow, objects []datastore.ObjectInfo, prefix string) Drift {
	have := map[string]bool{}
	var d Drift
	for _, o := range objects {
		if prefix != "" && len(o.Key) >= len(prefix) && o.Key[:len(prefix)] != prefix {
			continue
		}
		have[o.Key] = true
		if _, ok := rows[o.Key]; !ok {
			d.Orphaned = append(d.Orphaned, o.Key)
		}
	}
	for ref := range rows {
		if !have[ref] {
			d.Missing = append(d.Missing, ref)
		}
	}
	sort.Strings(d.Missing)
	sort.Strings(d.Orphaned)
	return d
}

// MetadataRows loads artifact/memory object references.
func MetadataRows(ctx context.Context, conn *pgx.Conn) (map[string]ObjectRow, error) {
	out := map[string]ObjectRow{}
	rows, err := conn.Query(ctx, `SELECT 'artifacts', object_ref, coalesce(checksum,'') FROM artifacts WHERE object_ref <> ''
		UNION ALL SELECT 'memory', object_ref, '' FROM memory WHERE object_ref <> ''`)
	if err != nil {
		return out, err
	}
	defer rows.Close()
	for rows.Next() {
		var r ObjectRow
		if err := rows.Scan(&r.Table, &r.Ref, &r.Checksum); err != nil {
			return out, err
		}
		out[r.Ref] = r
	}
	return out, rows.Err()
}

// RepairMissing deletes metadata rows whose object is absent (never deletes objects).
func RepairMissing(ctx context.Context, conn *pgx.Conn, rows map[string]ObjectRow, d Drift) (int64, error) {
	var n int64
	for _, ref := range d.Missing {
		r, ok := rows[ref]
		if !ok || (r.Table != "artifacts" && r.Table != "memory") {
			continue
		}
		tag, err := conn.Exec(ctx, fmt.Sprintf(`DELETE FROM %s WHERE object_ref = $1`, r.Table), ref)
		if err != nil {
			return n, err
		}
		n += tag.RowsAffected()
	}
	return n, nil
}
