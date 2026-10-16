-- EDP relationships (BI-PF-1408): referential links between domain tables.
-- Added where the parent table exists and is empty/safe to constrain. tenant_id on append-only tables
-- (audit, ledger) is intentionally left WITHOUT an FK (must record events even for deleted/unknown tenants).

ALTER TABLE derived_outputs ADD CONSTRAINT fk_derived_outputs_project
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL;
ALTER TABLE derived_outputs ADD CONSTRAINT fk_derived_outputs_run
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE SET NULL;

ALTER TABLE traceability ADD CONSTRAINT fk_traceability_item
    FOREIGN KEY (item_id) REFERENCES backlog_items(id) ON DELETE CASCADE;

ALTER TABLE jobs ADD CONSTRAINT fk_jobs_tenant
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
