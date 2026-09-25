# Pending Tasks

_Last updated: 2026-08-23_

## ✅ DONE

- [x] Remove `default_agent: ideation` from `opencode.json` — **DONE by user**
- [x] Design checkpoint/resume system for pipeline

## 🔧 HIGH PRIORITY — Core Fixes

### 1. Fix `opencode.json` — Add ZenFree Provider
**File:** `opencode.json`
**Status:** NEEDS WORK — user removed `default_agent`, but zenfree provider config not added yet

Add the `opencode` provider for zenfree models:
```json
"opencode": {
  "name": "OpenCode Zen",
  "options": {
    "baseURL": "https://opencode.ai/zen/v1"
  }
}
```

### 2. Update `/models` Command — Fix Model Override
**File:** `.opencode/command/models.md`
**Status:** NEEDS WORK — Line 4 has `model: opencode-go/mimo-v2.5` which blocks execution when quota is exhausted

Change to a zenfree model so the command itself can always run:
```yaml
model: opencode/ox-alpha-free
```

### 3. Switch All Agent Files to ZenFree Tier
**Files:** `.opencode/agent/*.md` (8 files)
**Status:** NEEDS WORK

| File | Current Model | New Model (zenfree) |
|---|---|---|
| `ideation.md` | opencode-go/mimo-v2.5 | opencode/ox-alpha-free |
| `design.md` | opencode-go/minimax-m3 | opencode/mimo-v2.5-free |
| `architect.md` | opencode-go/qwen3.7-max | opencode/nemotron-3-ultra-free |
| `review.md` | opencode-go/qwen3.7-plus | opencode/big-pickle |
| `implement.md` | opencode-go/kimi-k2.7-code | opencode/laguna-s-2.1-free |
| `code-review.md` | opencode-go/kimi-k2.7-code | opencode/big-pickle |
| `validate.md` | opencode-go/deepseek-v4-flash | opencode/mimo-v2.5-free |
| `fix.md` | opencode-go/kimi-k2.7-code | opencode/laguna-s-2.1-free |

### 4. Update Dashboard Default Models
**File:** `dashboard.html`
**Status:** NEEDS WORK — Line 125-133 has hardcoded `opencode-go/` models in the `AG` array

Update the `m:` field in each agent object to match zenfree models.

---

## 🆕 NEW FEATURES — Checkpoint & Resume System

### 5. Create Agent Context File Template
**New file:** `products/{product}/docs/agent-context.md`
**Status:** NOT STARTED

This file saves the pipeline state so it can resume after a session interruption.

Template:
```markdown
# Agent Context — Resume State

_Last updated: {timestamp}_

## Current State
| Field | Value |
|---|---|
| Current Stage | Stage X - Name |
| Current Agent | agent-id |
| Current Subtask | Description of what was being done |
| Started At | YYYY-MM-DD HH:MM:SS |
| Tokens Used | 0 |

## Pending Tasks
- [ ] Task 1
- [ ] Task 2

## Collected Inputs
- Key: Value

## Files In Progress
- path/to/file (status)

## User Responses Collected
1. Q: Question? A: Answer
```

### 6. Add Token Tracking to Pipeline
**File:** Orchestrator agent instructions (`ideation.md`)
**Status:** NOT STARTED

Add instructions for the orchestrator to:
- Record token usage after each agent completes (from Task tool response metadata)
- Record start time before invoking each agent via Task tool
- Record end time when Task tool returns
- Calculate duration = end - start
- Write all data to `agent-context.md` and `pipeline-state.md`

### 7. Update `pipeline-state.md` Format
**File:** `products/{product}/docs/pipeline-state.md`
**Status:** NOT STARTED

Add columns:
| Date/time | Request | Stage | Agent | Status | Artifact | Tokens | Start Time | End Time | Duration |

### 8. Update `agent-audit.md` Format
**File:** `products/{product}/docs/agent-audit.md`
**Status:** NOT STARTED

Add columns:
| Timestamp | Stage | Agent | Action | Status | Artifact | Tokens | Start | End | Duration |

### 9. Add Resume Logic to Orchestrator
**File:** Orchestrator agent instructions (`ideation.md`)
**Status:** NOT STARTED

Add these rules:

#### On Pipeline Start (fresh or resume):
1. Read `agent-context.md` if it exists
2. If there's an active stage (not completed), offer to resume
3. If user says resume, load context and continue from pending tasks
4. If user says start fresh, clear context and begin from Stage 0

#### Checkpointing (after each agent completes):
1. Before invoking agent: save start time to context
2. After agent returns: save end time, duration, tokens
3. Write updated context to `agent-context.md`
4. Update `pipeline-state.md` with timing data

#### Context to Save Per Checkpoint:
- Current stage number and name
- Which agent is running
- What subtask within the stage
- Start timestamp
- Tokens used so far (cumulative)
- Files being modified
- User inputs/responses collected
- List of pending tasks within current stage

### 10. Update Dashboard — Agent Runtime Display
**File:** `dashboard.html`
**Status:** NOT STARTED

Add to each agent card:
- **Start Time**: When the agent was invoked
- **End Time**: When the agent completed
- **Runtime**: Calculated duration (e.g., "2m 34s")
- **Tokens Used**: From pipeline-state.md

Current agent card layout (line 331):
```
Iterations | Tokens | Artifacts
```

New layout:
```
Iterations | Tokens | Runtime | Artifacts
```

### 11. Update Dashboard — Resume UI
**File:** `dashboard.html`
**Status:** NOT STARTED

Add a "Resume Available" banner when `agent-context.md` exists with pending tasks:
```html
<div class="resume-banner" id="resumeBanner" style="display:none">
  <h3>🔄 Pipeline Interrupted</h3>
  <p>Stage X was in progress. <span id="resumeDetails"></span></p>
  <button onclick="resumePipeline()">Resume from Last Checkpoint</button>
  <button onclick="startFresh()">Start Fresh</button>
</div>
```

### 12. Update Dashboard — Parse New Columns
**File:** `dashboard.html`
**Status:** NOT STARTED

Update `parsePS()` function (line 175) to parse the new columns (Tokens, Start, End, Duration) from `pipeline-state.md`.

Update `parseAudit()` function (line 180) to parse new columns from `agent-audit.md`.

---

## 📋 EXECUTION ORDER

When resuming, complete tasks in this order:

1. **Task 1** — Add zenfree provider to `opencode.json`
2. **Task 2** — Fix `/models` command model override
3. **Task 3** — Update all 8 agent files to zenfree tier
4. **Task 4** — Update dashboard hardcoded models
5. **Task 5** — Create `agent-context.md` template
6. **Tasks 7 & 8** — Update pipeline-state.md and agent-audit.md formats
7. **Tasks 6 & 9** — Add token tracking + resume logic to orchestrator
8. **Tasks 10, 11, 12** — Update dashboard for runtime, resume UI, new column parsing

---

## 🔍 VERIFICATION

After all changes, verify by:
1. Run `/models list` — all agents should show zenfree models
2. Run `/pipeline "test idea"` — should use zenfree models
3. Exit session mid-pipeline, rejoin — should offer resume
4. Open dashboard — should show runtime, tokens, resume banner
