-- EDP-15 C1b alignment (BI-PF-1307): align `artifacts` with the datastore.Artifact port
-- ({ID, TenantID, Project, Run, Stage, Type, ObjectRef, Checksum, Size, Version}).
--
-- Decisions: the object key is the content address (checksum), so ObjectRef needs no column (ObjectRef == checksum);
-- `version`(int) becomes the logical `revision`; the object store's version is `object_version`; add `artifact_type`
-- and `stage`. Retention/expiry stays EDP-16.

ALTER TABLE artifacts RENAME COLUMN version TO revision;
ALTER TABLE artifacts ADD COLUMN object_version TEXT NOT NULL DEFAULT '';
ALTER TABLE artifacts ADD COLUMN artifact_type  TEXT NOT NULL DEFAULT '';
ALTER TABLE artifacts ADD COLUMN stage          TEXT NOT NULL DEFAULT '';

DROP INDEX IF EXISTS uq_artifacts_name_version;
CREATE UNIQUE INDEX uq_artifacts_name_revision ON artifacts (tenant_id, name, revision);
