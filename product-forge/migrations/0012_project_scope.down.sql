-- Down for 0012_project_scope (BI-PF-1421): drop the direct scope/project_id discriminators.
DROP INDEX IF EXISTS idx_attempts_project;
ALTER TABLE attempts DROP COLUMN IF EXISTS project_id;

DROP INDEX IF EXISTS idx_stages_project;
ALTER TABLE stages DROP COLUMN IF EXISTS project_id;

DROP INDEX IF EXISTS idx_backlog_items_scope_project;
ALTER TABLE backlog_items DROP COLUMN IF EXISTS project_id;
ALTER TABLE backlog_items DROP COLUMN IF EXISTS scope;
