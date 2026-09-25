# Orchestrator Rules & Responsibilities

The Pipeline Orchestrator is the central control system that manages the entire pipeline execution. It is NOT an agent — it does NOT generate artifacts. It COORDINATES, MONITORS, and ENFORCES rules.

---

## Core Responsibilities

### 1. Human-in-the-Loop (HITL) — MANDATORY BY DEFAULT

**Rule:** Every agent's output MUST be reviewed and approved by a human before the pipeline proceeds to the next agent.

**Default Behavior:**
- `auto_approve: false` (default for ALL projects)
- After each agent completes → pipeline PAUSES
- Human reviews artifacts → approves/rejects/modifies
- Pipeline resumes only after approval

**Override Behavior:**
- When creating project, set `auto_approve: true` to skip HITL
- Only allowed for non-critical projects (prototyping, testing)
- NOT allowed for production deployments

**Approval Flow:**
```
Agent completes work
  ↓
Artifacts saved to: artifacts/{stage}/{agent}-output.md
  ↓
Approval request created: approvals/{stage}/{agent}-approval.json
  ↓
Pipeline PAUSES (status: waiting_approval)
  ↓
Human reviews artifacts
  ↓
Human approves via CLI: python approve.py --stage {stage} --agent {agent} --approve
  ↓
Pipeline RESUMES
```

**Approval Request Format:**
```json
{
  "request_id": "approval-20260910-120000",
  "stage_id": "2",
  "agent_id": "architect",
  "status": "pending",
  "artifacts": ["products/myworld/artifacts/2/architect-output.md"],
  "created_at": "2026-09-10T12:00:00",
  "review_instructions": "Review architecture document. Check: component design, file structure, technology stack.",
  "approved_by": null,
  "approved_at": null,
  "notes": ""
}
```

---

### 2. Time Management — DYNAMIC TIMEOUT

**Rule:** Orchestrator MUST track time and make intelligent decisions about continuation.

**Responsibilities:**
- Track `pipeline_start_time` at pipeline start
- Track `stage_durations` history
- Calculate `elapsed_time` after each stage
- Estimate `remaining_time` based on historical average
- Decision logic:
  - If `elapsed + estimated_remaining < max_total_time` → CONTINUE
  - If `elapsed + estimated_remaining >= max_total_time` → FINALIZE (skip remaining)
  - Always complete current stage before deciding

**Time Budget:**
```
Default max_total_time: 1800s (30 min)
Per-stage timeout: 300s (5 min)
Minimum remaining time to continue: 120s (2 min)
```

---

### 3. Stage Orchestration — DAG-BASED EXECUTION

**Rule:** Follow dependency graph. Run independent stages in parallel when possible.

**Responsibilities:**
- Parse DAG from pipeline-definition.json
- Track stage status (pending/ready/running/completed/failed/skipped)
- Execute ready stages (respect dependencies)
- Parallel execution for independent stages (max 3 concurrent)
- Mark stages as completed/failed based on agent results

---

### 4. Budget Enforcement — PER-STAGE AND TOTAL

**Rule:** Never exceed budget limits. Warn at 80%, stop at 100%.

**Responsibilities:**
- Create budget per stage from pipeline-definition.json
- Check budget before each agent execution
- Track actual spend vs budget
- Trigger conservation mode at thresholds:
  - 70%: NORMAL → reduce to cheaper models
  - 85%: CONSERVATIVE → skip non-essential agents
  - 95%: EMERGENCY → finalize immediately

---

### 5. Quality Gates — COMPLIANCE CHECK

**Rule:** All artifacts must pass compliance checks before proceeding.

**Responsibilities:**
- Run compliance check after each agent
- Check against agent contracts (context_manager.py)
- Block pipeline if critical compliance failure
- Allow warnings with human override

---

### 6. Error Recovery — CIRCUIT BREAKER

**Rule:** Prevent infinite retries. Fail fast after repeated failures.

**Responsibilities:**
- Track failures per agent/stage
- Open circuit breaker after 3 consecutive failures
- Skip blocked agents
- Record failure reasons for debugging

---

### 7. State Persistence — CHECKPOINT/RESUME

**Rule:** Pipeline must be resumable after interruption.

**Responsibilities:**
- Save state after each stage completion
- Track: completed stages, artifacts, costs, approvals
- On restart: resume from last completed stage
- State file: `pipeline-state.json`

---

### 8. Approval Gates — PIPELINE-DEFINED CHECKPOINTS

**Rule:** Honor approval gates defined in pipeline-definition.json.

**Gate Types:**
- `AG-scope-change`: After scope definition (Stage 1)
- `AG-architecture`: After architecture design (Stage 2)
- `AG-security-critical`: Before security review (Stage 5)
- `AG-deploy`: Before deployment (Stage 10, 11)

**Flow:**
```
Stage completes → Check if approval_gate defined
  ↓ YES
Create approval request → Pause pipeline
  ↓
Human approves via CLI or web UI
  ↓
Pipeline continues
```

---

### 9. Parallel Execution — INDEPENDENT STAGES

**Rule:** Maximize throughput by running independent stages concurrently.

**Constraints:**
- Max 3 concurrent stages (API rate limit safety)
- Shared budget across parallel stages
- No artifact dependencies between parallel stages
- Each parallel stage gets equal budget share

---

### 10. Self-Monitoring — HEALTH CHECK

**Rule:** Orchestrator must monitor its own health and report issues.

**Responsibilities:**
- Track execution time per stage
- Track memory usage
- Log all decisions to audit log
- Generate health report at completion
- Alert on anomalies (stages taking 3x average time)

---

## Orchestration Modes

### Mode 1: Interactive (Default)
- Human approval required after each agent
- Pipeline pauses for review
- Best for: Production, critical projects

### Mode 2: Auto-Approve
- No human approval required
- Pipeline runs continuously
- Best for: Prototyping, testing, trusted configurations

### Mode 3: Semi-Automatic
- Human approval required only for approval gates
- Other agents auto-approved
- Best for: Balanced speed and control

---

## State Machine

```
INIT → PLANNING → EXECUTION → VERIFICATION → COMPLETION
                  ↓
            WAITING_APPROVAL (HITL)
                  ↓
            EXECUTION (resumed)
                  ↓
            FAILED (if rejected/error)
```

---

## Decision Matrix

| Situation | Action |
|---|---|
| Agent completes, auto_approve=false | PAUSE → wait for approval |
| Agent completes, auto_approve=true | CONTINUE to next agent |
| Agent fails | RETRY once → then SKIP |
| Budget exceeded at 70% | SWITCH to cheaper model |
| Budget exceeded at 95% | FINALIZE immediately |
| Stage time > 3x average | WARN → continue |
| Pipeline time > 80% budget | SKIP remaining non-essential stages |
| Circuit breaker open | SKIP blocked agent |
| Approval gate reached | PAUSE → wait for gate approval |
| All stages complete | FINALIZE → generate report |

---

## Configuration

### Project Config (project.json)
```json
{
  "auto_approve": false,
  "max_total_time": 1800,
  "parallel_stages": 3,
  "approval_mode": "interactive"
}
```

### Pipeline Config (pipeline-definition.json)
```json
{
  "stages": {
    "2": {
      "approval_gate": "AG-architecture",
      "budget_limit": 3.0
    }
  }
}
```
