# Audit Register Triage (BI-PF-0254)

> Dispositions the audit register (`Product_Forge_Audit_...20260929.md`: PF-001–PF-521 + candidate batches
> A–CC) against what has been **fixed**, **tracked (backlog)**, or is **new**. Source of truth for a finding =
> the code; this doc records disposition, not the finding.

## Legend
- **FIXED** — implemented + tested (M0 / F1 / F2 work; see the referenced backlog item).
- **TRACKED** — open backlog item owns it.
- **NEW** — not yet represented; to be raised as an issue/backlog item.

## By workstream / family
| Family | Disposition | Where |
|---|---|---|
| Approvals / HIL fail-open (PF-001, BV-C01, PF-151) | **FIXED** (PF-151 partial) | `BI-PF-0237`; PF-151 → F0-5 tracker |
| Completion / verification truth (PF-036, PF-039, PF-060, PF-069, PF-145, PF-157, PF-158, BU-C07, BZ-C04, BW-C01) | **FIXED** | `BI-PF-0238` |
| Run-bound provenance & resume (PF-006, PF-031, BU-C06, CB-C01, CB-C02, BV-C05) | **FIXED** | `BI-PF-0239` |
| Transactional state / locks / queues (PF-011–016, PF-024, PF-025, PF-026, PF-032, PF-033) | **FIXED** | `BI-PF-0240` |
| Backlog transaction journal + migration manifest (BU-C02, BZ-C01 partial, BZ-C02) | **TRACKED** | `BI-PF-0240` (remaining) |
| Authorization at boundary (PF-004, BV-C02, PF-021, PF-023, PF-227) | **FIXED** | `BI-PF-0241` |
| Tenant-scoped authz / websocket / registry HIL (PF-022, PF-027, PF-123/124/125) | **TRACKED** | `BI-PF-0241` (remaining) |
| Budget/model/delegation (PF-013, PF-017, PF-067, PF-147) | **FIXED** (PF-013 mechanism) | `BI-PF-0242` |
| Context caps / substitution / delegation double-invoke (PF-019, PF-038, PF-154, PF-155, PF-204) | **TRACKED** | `BI-PF-0242` (remaining) |
| Execution contract + acceptance suite (M0.7) | **FIXED** | `BI-PF-0243` |
| Logs/events SSOT + run_id + query (PF-007/020/149/200/224/228) | **FIXED** | `BI-PF-0233/0234/0235` |
| Section D observability (OTel/trace/SLIs/retention/redaction) | **FIXED** | `BI-PF-0244` |
| Docs generator truth (BX-C01–C04, PF-174) | **TRACKED** | `BI-PF-0249` (partial: `--check` exit fixed) |
| CLI correctness (BW-C02/C03/C05/C06, CB-C04/C05, PF-161) | **TRACKED** | `BI-PF-0250` |
| Packaging / archival (PF-094/096/135/175, `.bak_pre_*`) | **TRACKED** | `BI-PF-0251` |
| Agent-card consistency (PF-130/131/143/168–170/176–178/190/196/203/205) | **TRACKED** | `BI-PF-0252` |
| Generated-script exit codes (PF-138/142/171/172/195) | **FIXED** (partial) | `BI-PF-0253` (run_e2e/audit_dependencies/migrate_backlog); rest tracked |
| Register triage (this doc) | **FIXED** | `BI-PF-0254` |
| Hygiene (artifacts/log paths/cp1252/CI/docs-fresh) | **FIXED** | `BI-PF-0255–0259` |
| State consolidation | **TRACKED** | `BI-PF-0260` |
| Cost/latency + capability steering (PF-008, PF-012, PF-179, review §) | **TRACKED** | `BI-0221–0230`, `BI-PF-0245/0246/0247` |
| Security scanners / CI scanners (PF-090–098, PF-160, PF-206, PF-225) | **TRACKED** | `BI-PF-0251` / new |
| Intake/API (PF-028, PF-107–116, PF-159) | **TRACKED** | `BI-PF-0232` + F1 intake |
| Historical backups (CC-H01–H05) | **FIXED** (regression-tested) | `BI-PF-0243` acceptance + `BI-PF-0251` packaging |
| Batches AF–CC residual (many P2) | **PARTIAL** | covered where grouped above; residual = new/tracked per `BI-PF-0260`/`0251` |

> **Note:** PF-071–PF-078 are absent from the source register (documented). Candidate IDs (BV/BW/BX/BY/BZ/CB/CC)
> are dispositioned by family above; no duplicate permanent IDs are allocated here.
> Rule going forward: every new finding is raised as an **issue** (`IS-<TAG>-<nnn>`, `core/issues.py`) with a
> 1:1 backlog item + RCCA (see EOS §13).
