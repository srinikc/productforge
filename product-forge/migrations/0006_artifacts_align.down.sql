-- Rollback EDP-15 C1b alignment.

DROP INDEX IF EXISTS uq_artifacts_name_revision;
CREATE UNIQUE INDEX uq_artifacts_name_version ON artifacts (tenant_id, name, version);
ALTER TABLE artifacts DROP COLUMN stage;
ALTER TABLE artifacts DROP COLUMN artifact_type;
ALTER TABLE artifacts DROP COLUMN object_version;
ALTER TABLE artifacts RENAME COLUMN revision TO version;
