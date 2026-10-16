-- Rollback EDP relationships (BI-PF-1408).

ALTER TABLE jobs DROP CONSTRAINT IF EXISTS fk_jobs_tenant;
ALTER TABLE traceability DROP CONSTRAINT IF EXISTS fk_traceability_item;
ALTER TABLE derived_outputs DROP CONSTRAINT IF EXISTS fk_derived_outputs_run;
ALTER TABLE derived_outputs DROP CONSTRAINT IF EXISTS fk_derived_outputs_project;
