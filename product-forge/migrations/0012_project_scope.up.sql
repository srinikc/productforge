-- BI-PF-1421 (epic BI-PF-0451): direct project/scope discriminators so product/project data is queried
-- WITHOUT JSON extraction or joins (EDP-17 schema doc, §A.1 "scope TEXT + project TEXT discriminators").
--
-- Soft references (TEXT + index), NOT foreign keys: the backlog spans `product_forge` (no project) and
-- generated products whose id is a filesystem slug not necessarily registered in `projects`, so an FK would
-- reject writes/backfills. Integrity is enforced at the backlog/runs write boundary (the owner), per §A.3
-- ("soft refs, indexed"). Expand-only and reversible.

-- backlog_items: first-class scope + project_id
ALTER TABLE backlog_items ADD COLUMN scope TEXT NOT NULL DEFAULT 'product_forge';
ALTER TABLE backlog_items ADD COLUMN project_id TEXT;
UPDATE backlog_items SET
    scope      = COALESCE(NULLIF(data->>'scope', ''), 'product_forge'),
    project_id = NULLIF(data->>'project', '');
CREATE INDEX idx_backlog_items_scope_project ON backlog_items (scope, project_id);

-- stages: project_id denormalized from the owning run
ALTER TABLE stages ADD COLUMN project_id TEXT;
UPDATE stages s SET project_id = r.project_id FROM runs r WHERE r.id = s.run_id;
CREATE INDEX idx_stages_project ON stages (project_id);

-- attempts: project_id denormalized from the owning stage
ALTER TABLE attempts ADD COLUMN project_id TEXT;
UPDATE attempts a SET project_id = s.project_id FROM stages s WHERE s.id = a.stage_id;
CREATE INDEX idx_attempts_project ON attempts (project_id);
