package bench

import (
	"context"
	"errors"
	"time"

	"productforge/datastore"
	"productforge/store"
)

// ErrNoDSN is recorded on every DB-backed scenario when no DSN is configured (the harness still runs + reports).
var ErrNoDSN = errors.New("bench: PF_RUNTIME_DSN not set - DB scenario skipped")

const benchTenant = "t-bench"

// Groups returns the six EDP-06 operation groups.
func Groups() []string { return []string{"artifact", "project", "run", "memory", "job", "db"} }

type opFunc func(ctx context.Context, tx datastore.Tx, tenant string, i int) error

type scenario struct {
	group string
	name  string
	setup opFunc // run once before measuring (nil = none)
	run   opFunc // the op measured N times
}

func scenarios() []scenario {
	p := benchTenant + "-proj"
	return []scenario{
		// artifact: list + single read (stored_objects is the artifact byte store)
		{"artifact", "artifact.list", nil, func(ctx context.Context, tx datastore.Tx, t string, _ int) error {
			return drain(ctx, tx, `SELECT checksum FROM stored_objects WHERE tenant_id=$1 LIMIT 20`, t)
		}},
		{"artifact", "artifact.read", nil, func(ctx context.Context, tx datastore.Tx, t string, _ int) error {
			return drain(ctx, tx, `SELECT checksum, size, content_type FROM stored_objects WHERE tenant_id=$1 LIMIT 1`, t)
		}},
		// project: load + save
		{"project", "project.load", seedProject, func(ctx context.Context, tx datastore.Tx, t string, _ int) error {
			return drain(ctx, tx, `SELECT slug, name, status FROM projects WHERE tenant_id=$1 AND id=$2`, t, p)
		}},
		{"project", "project.save", nil, func(ctx context.Context, tx datastore.Tx, t string, _ int) error {
			return exec(ctx, tx, `INSERT INTO projects (id, tenant_id, slug, name, status, version)
				VALUES ($1,$2,$3,'bench','active',0)
				ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, version=projects.version+1, updated_at=now()`,
				p, t, p)
		}},
		// run: state transition (create/advance a run)
		{"run", "run.transitions", seedProject, func(ctx context.Context, tx datastore.Tx, t string, i int) error {
			status := "queued"
			if i%2 == 1 {
				status = "running"
			}
			return exec(ctx, tx, `INSERT INTO runs (id, tenant_id, project_id, status, spec, version)
				VALUES ($1,$2,$3,$4,'{}'::jsonb,0)
				ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, version=runs.version+1, updated_at=now()`,
				t+"-run", t, p, status)
		}},
		// memory: retrieval (insert + scoped read)
		{"memory", "memory.retrieval", seedProject, func(ctx context.Context, tx datastore.Tx, t string, _ int) error {
			if err := exec(ctx, tx, `INSERT INTO memory (id, tenant_id, project_id, kind, acl_scope, payload)
				VALUES ($1,$2,$3,'note','team','{}'::jsonb) ON CONFLICT (id) DO NOTHING`, t+"-mem", t, p); err != nil {
				return err
			}
			return drain(ctx, tx, `SELECT id FROM memory WHERE tenant_id=$1 AND acl_scope='team' LIMIT 10`, t)
		}},
		// job: claim + lease
		{"job", "job.claim_lease", nil, func(ctx context.Context, tx datastore.Tx, t string, _ int) error {
			if err := exec(ctx, tx, `INSERT INTO jobs (id, tenant_id, kind, status) VALUES ($1,$2,'bench','queued')
				ON CONFLICT (id) DO NOTHING`, t+"-job", t); err != nil {
				return err
			}
			if err := exec(ctx, tx, `UPDATE jobs SET status='leased', lease_id=$2, expires_at=now()+interval '60s',
				updated_at=now() WHERE id=$1`, t+"-job", "w-bench"); err != nil {
				return err
			}
			return exec(ctx, tx, `UPDATE jobs SET status='completed', updated_at=now() WHERE id=$1`, t+"-job")
		}},
		// db: pool/table counts
		{"db", "db.pool_counts", nil, func(ctx context.Context, tx datastore.Tx, t string, _ int) error {
			if err := drain(ctx, tx, `SELECT count(*) FROM backlog_items WHERE tenant_id=$1`, t); err != nil {
				return err
			}
			return drain(ctx, tx, `SELECT count(*) FROM stored_objects WHERE tenant_id=$1`, t)
		}},
	}
}

func seedProject(ctx context.Context, tx datastore.Tx, t string, _ int) error {
	return exec(ctx, tx, `INSERT INTO projects (id, tenant_id, slug, name, status, version)
		VALUES ($1,$2,$3,'bench','active',0) ON CONFLICT (id) DO NOTHING`, t+"-proj", t, t+"-proj")
}

func seedTenant(ctx context.Context, tx datastore.Tx, t string) error {
	return exec(ctx, tx, `INSERT INTO tenants (id, slug, name, region, status) VALUES ($1,$1,$1,'','active')
		ON CONFLICT (id) DO NOTHING`, t)
}

func exec(ctx context.Context, tx datastore.Tx, sql string, args ...any) error {
	_, err := tx.Exec(ctx, sql, args...)
	return err
}

func drain(ctx context.Context, tx datastore.Tx, sql string, args ...any) error {
	rows, err := tx.Query(ctx, sql, args...)
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
	}
	return rows.Err()
}

// RunAll measures every scenario (ops iterations each) and, when outPath != "", writes the versioned baseline
// report there. Without a DSN the scenarios are skipped (ErrNoDSN) but the report is still produced.
func RunAll(ctx context.Context, dsn, outPath string, ops int) (Report, error) {
	rep := Report{Version: BaselineVersion, GeneratedAt: time.Now().UTC(), DSN: dsn}
	if dsn == "" {
		for _, s := range scenarios() {
			rep.Results = append(rep.Results, Result{Group: s.group, Scenario: s.name, Err: ErrNoDSN.Error()})
		}
		return rep, nil
	}
	st, err := store.Open(ctx, dsn)
	if err != nil {
		return rep, err
	}
	defer st.Close()
	var bind datastore.RelationalStore = store.BindTenant(st, benchTenant)
	if err := bind.WithTx(ctx, func(tx datastore.Tx) error { return seedTenant(ctx, tx, benchTenant) }); err != nil {
		return rep, err
	}
	for _, s := range scenarios() {
		if s.setup != nil {
			if err := bind.WithTx(ctx, func(tx datastore.Tx) error { return s.setup(ctx, tx, benchTenant, 0) }); err != nil {
				rep.Results = append(rep.Results, Result{Group: s.group, Scenario: s.name, Err: err.Error()})
				continue
			}
		}
		run := s.run
		rep.Results = append(rep.Results, Measure(s.group, s.name, ops, func(i int) error {
			return bind.WithTx(ctx, func(tx datastore.Tx) error { return run(ctx, tx, benchTenant, i) })
		}))
	}
	if outPath != "" {
		if err := WriteReport(outPath, rep); err != nil {
			return rep, err
		}
	}
	return rep, nil
}

// RunAllWithSink measures + writes the report, then publishes it to sink so the metrics reach the
// observability/SLO store (EDP-22). A nil sink is a no-op (report captured + artifact written, not published).
func RunAllWithSink(ctx context.Context, dsn, outPath string, ops int, sink Sink) (Report, error) {
	rep, err := RunAll(ctx, dsn, outPath, ops)
	if err != nil {
		return rep, err
	}
	if err := Publish(ctx, sink, rep); err != nil {
		return rep, err
	}
	return rep, nil
}
