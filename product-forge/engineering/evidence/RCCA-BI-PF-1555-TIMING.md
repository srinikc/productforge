# RCCA — Execution Timing Overhead on BI-PF-1555 (5-Why & Preventive Guards)

## 1. Summary
- **Item:** `BI-PF-1555` (*Plane A One-Click Cloud Provisioner*)
- **Total Duration:** ~55 minutes
- **Breakdown:** Gate 0 (~1m), Gate 1.5 (~26m), Gate 1 (~1m), Implementation (~3m), Gate 2.5 (~19m), Gate 2 / Delivery (~2m), Precheck fast runs (~3m).
- **Core Observation:** Actual implementation took ~3 minutes, while gate reconciliation, contract validation, and review iteration took ~45 minutes (>80% of total time).

---

## 2. 5-Why Root Cause Analysis

1. **Why was total duration ~55 minutes for a 3-minute implementation?**
   Gate 1.5 spec-contract freezing (~26 min) and Gate 2.5 review iterations (~19 min) required multiple sequential rounds of error correction.
2. **Why were multiple rounds of correction required during Gate 1.5 and Gate 2.5?**
   Because gates failed closed on schema non-compliance (missing control attributes like `applies_to`, `pytest::` prefixes, `candidate_sha` parity, and missing `fix_impact` rows for latest review findings).
3. **Why were schema attributes and fix-impact rows missing on first pass?**
   The spec, design contract, and controls were initially written iteratively rather than referencing the fully unified schema contract (`config/design-pack.json` and `config/fix-impact.json`) in a single pass.
4. **Why did Gate 2.5 require re-reviews and additional iterations?**
   Post-implementation bug fixes (e.g. EKS IAM policies, paths-contract in `deploy_plane_a.py`) updated code files, altering `candidate_sha` and `diff_sha`, which invalidated prior Gate 2.5 reviews and triggered new review findings.
5. **Root Cause:**
   Absence of a **validated single-pass authoring standard** that binds all required control schema fields, freeze hashes, and fix-impact synchronization upfront, combined with shell environment token dropouts that caused transient 401s during automated tooling execution.

---

## 3. Preventive Guards for BI-PF-1556

1. **Guard 1 (Single-Pass Complete Spec & Design Authoring):**
   Author `engineering/specs/BI-PF-1556.md`, `engineering/specs/BI-PF-1556-spec-pack.md`, and `engineering/design/BI-PF-1556.md` synchronously with all control-matrix fields (`id`, `kind`, `dimension`, `applies_to`, `check` with pytest target, `failure_behavior`, `owner`) and FR IDs (`FR-1`, `FR-2`, `FR-3`) in pass 1.
2. **Guard 2 (Synchronous Candidate SHA Parity):**
   Set `candidate_sha` to the active branch commit hash across all design pack controls, AC evidence, and traceability tables simultaneously before freezing.
3. **Guard 3 (Immediate Fix-Impact Dispositioning):**
   Immediately after Gate 2.5 emits findings, parse any MAJOR/BLOCKER findings and write their `fix_impact` entries (`sig`, `finding`, `status="ACTIONED"`, `evidence`, `reproducer`, `origin_class`, `artifacts_updated`) directly into the DB and disk mirror before running `precheck.py`.
4. **Guard 4 (Direct Token Ingestion):**
   Always inject `$env:PF_EDP_TOKEN` and `$env:PF_ADMIN_TOKEN` directly in the PowerShell environment block without outer subshell interpolation to prevent 401 authentication errors.
