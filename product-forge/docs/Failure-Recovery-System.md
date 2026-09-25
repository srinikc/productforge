# Failure Recovery System

## Quick Reference

| Component | Purpose | When Used | How to Check |
|---|---|---|---|
| **Checkpoints** | Save pipeline state | After each agent completes | `python scripts/pipeline.py checkpoints` |
| **Dead Letter Queue (DLQ)** | Store permanently failed tasks | After retry exhaustion | `python scripts/pipeline.py dlq` |
| **Circuit Breakers** | Stop cascading failures | After 5+ consecutive failures | `python scripts/pipeline.py health` |

## Overview

The Failure Recovery System provides automatic detection, recovery, and manual override capabilities for agent/pipeline failures. It ensures that stuck, crashed, or failed agents are detected and can be recovered automatically or manually.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FAILURE DETECTION LAYER                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Timeout    │  │   Health     │  │   Output     │          │
│  │   Detector   │  │   Monitor    │  │   Validator  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
├─────────────────────────────────────────────────────────────────┤
│                    RECOVERY DECISION LAYER                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Classifier │  │   Circuit    │  │   Checkpoint │          │
│  │   (T/P/S/C)  │  │   Breaker   │  │   Manager    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
├─────────────────────────────────────────────────────────────────┤
│                    RECOVERY ACTION LAYER                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Retry      │  │   Fallback   │  │   Dead       │          │
│  │   +Backoff   │  │   Chain      │  │   Letter Q   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
├─────────────────────────────────────────────────────────────────┤
│                    VISIBILITY LAYER                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Dashboard  │  │   /pipeline  │  │   Alerts     │          │
│  │   Health     │  │   Status     │  │   & Logs     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

## Failure Types & Responses

| Failure Type | Detection | Auto Recovery | Manual Override |
|--------------|-----------|---------------|-----------------|
| **Agent Timeout** | Per-tool timeout (configurable) | Retry with backoff, fallback model | `/pipeline fix <agent>` |
| **Agent Crash** | Startup recovery, orphan cleanup | Resume from checkpoint | `/pipeline resume <stage>` |
| **Provider Rate Limit** | HTTP 429, quota errors | Fallback chain, cooldown | `/pipeline model <provider>` |
| **Invalid Output** | Schema validation, quality check | Re-prompt with constraints | `/pipeline retry <agent>` |
| **Stuck Session** | Runtime watchdog (heartbeat) | Abort + checkpoint resume | `/pipeline abort <session>` |
| **Cascading Failure** | Circuit breaker (5 failures/60s) | Isolate, fail fast, fallback | `/pipeline circuit-reset` |

## Implementation Details

### A. Timeout Detection

Each agent has a configurable timeout:

| Agent | Default Timeout | Description |
|-------|----------------|-------------|
| ideation | 300000ms (5 min) | Idea gathering and questions |
| design | 600000ms (10 min) | Requirements and design |
| architect | 900000ms (15 min) | Architecture decisions |
| review | 300000ms (5 min) | Design review |
| implement | 1800000ms (30 min) | Code implementation |
| code-review | 600000ms (10 min) | Code review |
| validate | 600000ms (10 min) | Testing and validation |
| fix | 600000ms (10 min) | Bug fixes |

On timeout:
1. Abort the agent process
2. Synthesize tool-result with `metadata.timeout=true`
3. Create checkpoint with timeout state
4. Report to user with retry suggestion

### B. Startup Recovery

On server/pipeline start:
1. Query messages WHERE `time_completed IS NULL` AND `role = 'assistant'`
2. For each orphan:
   - Set `time_completed = Date.now()`
   - Set tool_parts `status = 'error'` with `error = 'Interrupted (restart)'`
   - Emit Bus events for UI update
3. Check for incomplete stages in pipeline.json
4. Report recovery status to user

### C. Circuit Breaker

The circuit breaker pattern prevents cascading failures:

**States:**
- **CLOSED**: Normal operation, calls pass through
- **OPEN**: Failing state, calls fail fast without invoking the agent
- **HALF_OPEN**: Testing state, a single probe call to check recovery

**Thresholds:**
- Open after 5 consecutive failures OR 50% error rate in 60 seconds
- Cooldown: 30-60 seconds before half-open
- Success in half-open → closed
- Failure in half-open → open

**Implementation:**
```javascript
// Check circuit breaker before execution
if (circuitBreaker.state === 'open') {
  // Wait for cooldown
  await sleep(circuitBreaker.cooldown);
  // Try probe call
  const success = await tryProbeCall(agent);
  if (success) {
    circuitBreaker.state = 'closed';
    circuitBreaker.failures = 0;
  } else {
    circuitBreaker.state = 'open';
    throw new Error('Circuit breaker open for agent: ' + agentName);
  }
}
```

### D. Checkpointing

After each stage completion, create a checkpoint:

```javascript
checkpoint = {
  id: `checkpoint-${Date.now()}`,
  type: 'stage', // or 'selective'
  agent: agentName,
  stage: stageNumber,
  input: inputSummary,
  output: outputSummary,
  timestamp: new Date().toISOString(),
  status: 'completed'
}
```

**Storage:**
- Checkpoints: `products/<project>/checkpoints/<checkpoint-id>.json`
- Pipeline state: `products/<project>/pipeline.json`

**Recovery:**
1. Load last valid checkpoint
2. Resume from `checkpoint.current_stage`
3. Continue pipeline execution

### E. Dead Letter Queue (DLQ)

When retry exhaustion occurs, add to DLQ:

```javascript
dlq_item = {
  id: `dlq-${Date.now()}`,
  agent: agentName,
  input: inputPayload,
  error: {
    code: errorCode,
    message: errorMessage,
    stack: errorStack
  },
  attempts: retryCount,
  timestamps: [timestamp1, timestamp2, ...],
  checkpoint_id: lastCheckpointId
}
```

**Storage:** `products/<project>/dlq/<dlq-id>.json`

**Replay:** `/pipeline dlq replay <dlq-id>` reprocesses the failed task

### F. Fallback Chain

When a provider fails, try fallback models:

```javascript
fallback_chains = {
  ideation: ['opencode-go/mimo-v2.5', 'openrouter/claude-sonnet'],
  design: ['opencode-go/mimo-v2.5', 'openrouter/claude-sonnet'],
  // ...
}
```

**Logic:**
1. Try primary model
2. On retryable failure (rate limit, timeout):
   - Mark primary as cooling down (5min default, 6h for quota)
   - Try next model in chain
   - If all on cooldown: pick soonest expiry
3. On success: clear cooldown, update model attribution

## Dashboard Health Indicators

```
┌─────────────────────────────────────────────────────────────────┐
│  PIPELINE HEALTH: myworld                                       │
├─────────────────────────────────────────────────────────────────┤
│  Status: 🟡 DEGRADED (1 agent retrying)                         │
│                                                                 │
│  Agent Health:                                                  │
│  ┌─────────────┬──────────┬──────────┬──────────┬────────────┐ │
│  │ Agent       │ Status   │ Attempts │ Fallback │ Circuit    │ │
│  ├─────────────┼──────────┼──────────┼──────────┼────────────┤ │
│  │ ideation    │ ✅ OK    │ 1/1      │ -        │ CLOSED     │ │
│  │ design      │ ✅ OK    │ 1/1      │ -        │ CLOSED     │ │
│  │ architect   │ ⚠️ RETRY │ 2/3      │ flash→son│ HALF_OPEN  │ │
│  │ review      │ ✅ OK    │ 1/1      │ -        │ CLOSED     │ │
│  │ implement   │ ⏳ WAIT  │ -        │ -        │ CLOSED     │ │
│  │ validate    │ ⏳ WAIT  │ -        │ -        │ CLOSED     │ │
│  │ fix         │ ⏳ WAIT  │ -        │ -        │ CLOSED     │ │
│  └─────────────┴──────────┴──────────┴──────────┴────────────┘ │
│                                                                 │
│  Recent Events:                                                 │
│  • 14:32:15 architect timeout (600s exceeded) → retry #1       │
│  • 14:32:45 architect rate_limit → fallback to sonnet           │
│  • 14:33:15 architect success (fallback model)                  │
│                                                                 │
│  Dead Letter Queue: 0 items                                     │
│  Checkpoints: 3 saved (stages 0, 1, 2)                         │
│  Last checkpoint: 14:30:00 (stage 2 complete)                   │
└─────────────────────────────────────────────────────────────────┘
```

## /pipeline Health Commands

```
/pipeline                    → Show project picker + health summary
/pipeline status             → Detailed health for current project
/pipeline status <project>   → Detailed health for specific project
/pipeline health             → Same as status (alias)
/pipeline dlq                → Show dead letter queue items
/pipeline dlq replay <id>    → Reprocess failed task
/pipeline circuit-reset      → Reset all circuit breakers
/pipeline circuit-status     → Show circuit breaker states
/pipeline checkpoints        → List saved checkpoints
/pipeline resume <checkpoint>→ Resume from specific checkpoint
/pipeline retry <agent>      → Manually retry failed agent
/pipeline abort <agent>      → Abort stuck agent
/pipeline run-agent <agent>  → Auto-diagnose and fix agent
```

## Selective Run Failure Handling

When a selective run fails:
1. Create checkpoint with error state
2. Show in dashboard with error details
3. Allow resume from checkpoint
4. Allow rerun with same input

```javascript
// On failure during selective run
async function handleSelectiveRunFailure(
  project,
  agentName,
  error,
  input
) {
  // Create failure checkpoint
  const checkpointId = await createSelectiveCheckpoint(
    project,
    agentName,
    input,
    `ERROR: ${error.message}`
  )
  
  // Update pipeline state
  await updatePipelineState(project, {
    lastSelectiveRun: {
      agent: agentName,
      status: 'failed',
      error: error.message,
      checkpointId
    }
  })
  
  // Emit event for dashboard
  emitEvent('selective-run-failed', {
    project,
    agent: agentName,
    error: error.message,
    checkpointId
  })
}
```

## Error Classification

Every error is classified before recovery:

| Class | Examples | Default Action |
|-------|----------|----------------|
| **transient** | HTTP 429, 5xx, network timeout, connection reset | Retry with backoff |
| **permanent** | HTTP 4xx (except 408/429), validation error, auth failure | No retry; escalate or fail |
| **semantic** | Tool returned syntactically valid but wrong-content output | Re-plan with constraints |
| **policy** | Safety / content / quota refusal | Fallback path; do not retry same input |
| **state** | Lost context, expired session, corrupted memory | Recover from checkpoint, then retry |

## Retry Strategy

For transient errors, use exponential backoff with jitter:

```javascript
// Exponential backoff with jitter
function getRetryDelay(attempt, baseDelay = 1000, maxDelay = 30000) {
  const exponentialDelay = Math.min(baseDelay * Math.pow(2, attempt), maxDelay);
  const jitter = Math.random() * exponentialDelay * 0.5; // ±25% jitter
  return exponentialDelay + jitter;
}

// Retry with budget
async function retryWithBackoff(fn, maxRetries = 3, retryBudget = 60000) {
  const startTime = Date.now();
  let lastError;
  
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    const elapsed = Date.now() - startTime;
    if (elapsed > retryBudget) {
      throw new Error('Retry budget exceeded');
    }
    
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      if (!isRetryable(error)) {
        throw error;
      }
      
      const delay = getRetryDelay(attempt);
      await sleep(delay);
    }
  }
  
  throw lastError;
}
```

## Monitoring & Observability

Track these metrics per agent role:
- **P50/P95/P99 latency**: Detects slowdown before timeout
- **Circuit breaker state transitions**: OPEN→HALF_OPEN→CLOSED
- **DLQ depth**: Growing DLQ means a systemic problem
- **Retry rate**: Spiking retries indicate rate limiting or degradation

## Configuration

### pipeline.json Structure

```json
{
  "name": "project-name",
  "circuit_breakers": {
    "agent-name": {
      "state": "closed",
      "failures": 0,
      "last_failure": null,
      "cooldown": 30000
    }
  },
  "fallback_chains": {
    "agent-name": ["primary-model", "fallback-model"]
  },
  "checkpoints": ["checkpoint-id-1", "checkpoint-id-2"],
  "selective_runs": ["run-id-1", "run-id-2"],
  "dlq": ["dlq-id-1", "dlq-id-2"]
}
```

### Timeouts

Configure per-agent timeouts in pipeline.json:

```json
{
  "timeouts": {
    "ideation": 300000,
    "design": 600000,
    "architect": 900000,
    "review": 300000,
    "implement": 1800000,
    "code-review": 600000,
    "validate": 600000,
    "fix": 600000
  }
}
```
