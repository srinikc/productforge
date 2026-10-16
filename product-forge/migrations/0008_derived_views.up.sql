-- EDP Slice C (BI-PF-1415): project/tenant-scoped derived stores as DB views over a generic
-- derived_outputs table (kind = the store name). RLS applies via the base table.

CREATE TABLE derived_outputs (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    project_id  TEXT,
    run_id      TEXT,
    kind        TEXT NOT NULL,
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_derived_outputs_kind ON derived_outputs (kind);
CREATE INDEX idx_derived_outputs_scope ON derived_outputs (tenant_id, project_id, kind);
ALTER TABLE derived_outputs ENABLE ROW LEVEL SECURITY;
ALTER TABLE derived_outputs FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON derived_outputs USING (tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

CREATE VIEW v_agents_live AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'agents-live.json';
CREATE VIEW v_analysis_report AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'analysis-report.json';
CREATE VIEW v_bom AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'BOM.json';
CREATE VIEW v_call_ledger AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'call-ledger.jsonl';
CREATE VIEW v_capabilities AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'capabilities-*.json';
CREATE VIEW v_cost_metrics AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'cost_metrics.jsonl';
CREATE VIEW v_cost_model AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'cost-model.json';
CREATE VIEW v_cycles AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'cycles.json';
CREATE VIEW v_design_spec AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'design-spec.json';
CREATE VIEW v_design_tokens AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'design-tokens.json';
CREATE VIEW v_discovery_questions AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'discovery-questions.json';
CREATE VIEW v_discovery_result AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'discovery-result.json';
CREATE VIEW v_docker_compose_generated AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'docker-compose.generated.json';
CREATE VIEW v_eap AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'eap.json';
CREATE VIEW v_extended_capabilities AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'extended-capabilities.json';
CREATE VIEW v_feasibility AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'feasibility.json';
CREATE VIEW v_features AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'features.json';
CREATE VIEW v_final AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'final.json';
CREATE VIEW v_final_report AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'final-report.json';
CREATE VIEW v_go_no_go AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'go-no-go.json';
CREATE VIEW v_id AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'history/<ID>.jsonl';
CREATE VIEW v_id_functional_md AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'changes/<ID>-functional.md';
CREATE VIEW v_idea_consolidation AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'idea-consolidation.json';
CREATE VIEW v_incidents AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'incidents.json';
CREATE VIEW v_index AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'INDEX.json';
CREATE VIEW v_index_md AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'INDEX.md';
CREATE VIEW v_model_fit AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'model-fit.json';
CREATE VIEW v_model_gate AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'model-gate.json';
CREATE VIEW v_model_strategy AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'model-strategy.json';
CREATE VIEW v_ops_report AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'ops-report.json';
CREATE VIEW v_ops_run AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'ops-run.json';
CREATE VIEW v_otel_spans AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'otel-spans.jsonl';
CREATE VIEW v_packaging_manifest AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'packaging-manifest.json';
CREATE VIEW v_pipeline AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'pipeline.json';
CREATE VIEW v_pipeline_execution_report AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'pipeline-execution-report.json';
CREATE VIEW v_pipeline_runs AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'pipeline-runs.json';
CREATE VIEW v_plan_review AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'plan-review.json';
CREATE VIEW v_ports AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'ports.json';
CREATE VIEW v_presentation AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'presentation.json';
CREATE VIEW v_project_status AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'project-status.json';
CREATE VIEW v_qa_manifest AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'qa-manifest.json';
CREATE VIEW v_qir AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'qir.json';
CREATE VIEW v_qir_history AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'qir-history.json';
CREATE VIEW v_quality_metrics AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'quality-metrics.json';
CREATE VIEW v_readiness AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'readiness.json';
CREATE VIEW v_release_manifest AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'release-manifest.json';
CREATE VIEW v_rerun_review AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'rerun-review.json';
CREATE VIEW v_run_id AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'run-manifests/<run_id>.json';
CREATE VIEW v_run_plan AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'run-plan.json';
CREATE VIEW v_run_status AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'run-status.json';
CREATE VIEW v_security_issues AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'security-issues.json';
CREATE VIEW v_sizing AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'sizing.json';
CREATE VIEW v_spec_review AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'spec-review.json';
CREATE VIEW v_stage AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = '_stage.json';
CREATE VIEW v_test_comments AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'test-comments.json';
CREATE VIEW v_test_cycle AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'test-cycle.json';
CREATE VIEW v_tokens AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'tokens.json';
CREATE VIEW v_trends AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'trends.json';
CREATE VIEW v_usage AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'usage.jsonl';
CREATE VIEW v_verification_html AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'verification.html';
CREATE VIEW v_work_estimate AS SELECT id, tenant_id, project_id, run_id, payload, computed_at FROM derived_outputs WHERE kind = 'work-estimate.json';

