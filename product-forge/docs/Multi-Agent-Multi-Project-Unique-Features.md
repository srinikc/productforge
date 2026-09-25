# Multi-Agent Multi-Project Pipeline — Unique Features

**Version:** 1.0
**Date:** 2026-08-24

---

## Overview

This document describes the unique features that distinguish this Multi-Agent Multi-Project Pipeline from traditional CI/CD pipelines and single-agent systems.

---

## 1. Multi-Project Isolation

### Feature
Each project gets its own isolated workspace with dedicated:
- `pipeline.json` configuration
- Documentation artifacts
- Checkpoints and state
- Model tier assignments
- Feature tracking

### Uniqueness
Unlike traditional pipelines that share configuration across projects, this system provides complete isolation. Each project can:
- Use different model tiers (recommended, cheap, hybrid, free)
- Have different agent enable/disable states
- Maintain separate feature lists and implementation status
- Run independently without affecting other projects

### Example
```
products/
├── myworld/           # Project 1: Full-stack web app
│   ├── pipeline.json  # Uses "recommended" tier
│   └── docs/
├── mobileapp/         # Project 2: Mobile app
│   ├── pipeline.json  # Uses "cheap" tier
│   └── docs/
└── api-service/       # Project 3: Microservice
    ├── pipeline.json  # Uses "hybrid" tier
    └── docs/
```

---

## 2. Selective Agent Execution

### Feature
Run specific agents individually without running the full pipeline:
```bash
/pipeline run documentation      # Run only documentation agent
/pipeline run api,db             # Run API and DB agents in parallel
/pipeline run ui --model X       # Run UI agent with specific model
```

### Uniqueness
Traditional pipelines run all stages sequentially. This system allows:
- **Granular control**: Run only the agents you need
- **Parallel execution**: Run multiple agents simultaneously
- **Model override**: Use different models for specific runs
- **Input/output routing**: Specify input sources and output targets

### Benefits
- **Cost savings**: Only pay for agents you actually run
- **Faster iteration**: Skip unnecessary stages
- **Flexibility**: Re-run specific agents without re-running entire pipeline
- **Testing**: Test individual components in isolation

---

## 3. Feature-Based Implementation with Sub-Agents

### Feature
The Implement agent orchestrates specialized sub-agents:
- **UI/UX Agent**: Frontend components, styling, user interactions
- **API Agent**: REST/GraphQL endpoints, request/response handling
- **DB Agent**: Database schema, migrations, queries
- **Business Logic Agent**: Core business rules, domain models

### Uniqueness
Unlike single-agent implementation, this system:
- **Delegates to specialists**: Each sub-agent focuses on its domain
- **Tracks feature status**: Real-time feature completion tracking
- **Ensures E2E implementation**: Features are fully implemented and tested
- **Maintains consistency**: Sub-agents follow architecture decisions

### Feature Tracking
```
Feature ID | Feature Name       | Module      | Sub-Agent | Status
-----------|-------------------|-------------|-----------|--------
F-001      | User Authentication| API         | API Agent | ✅ Done
F-002      | Login UI           | UI/UX       | UI Agent  | 🔄 In Progress
F-003      | User Database      | Database    | DB Agent  | ⏳ Pending
```

---

## 4. Living Product Plan

### Feature
`product-plan.md` is a living document updated by each agent:
- **Ideation**: Initial idea and requirements
- **Design**: User flows, wireframes, components
- **Architect**: Tech stack, architecture decisions, feature list
- **Implement**: Implementation status, files created
- **Review**: Code review findings
- **Validate**: Test results, issues found

### Uniqueness
Traditional documentation is static. This system:
- **Auto-updates**: Each agent updates the plan after completion
- **Maintains history**: Tracks changes over time
- **Provides single source of truth**: All agents reference the same document
- **Enables traceability**: Links features to requirements to implementation

---

## 5. Failure Recovery System

### Feature
Comprehensive failure detection and recovery:
- **Circuit Breakers**: Prevent cascading failures
- **Checkpoints**: Save and restore pipeline state
- **Dead Letter Queue**: Capture permanently failed tasks
- **Fallback Chains**: Try alternative models on failure

### Uniqueness
Unlike basic retry logic, this system:
- **Classifies errors**: Transient, permanent, semantic, policy, state
- **Automatic recovery**: Retries with exponential backoff
- **Manual override**: Human intervention when needed
- **State persistence**: Resume from any checkpoint

### Circuit Breaker States
```
CLOSED → (failures >= threshold) → OPEN
OPEN → (cooldown expired) → HALF_OPEN
HALF_OPEN → (probe success) → CLOSED
```

---

## 6. Health Monitoring Dashboard

### Feature
Real-time health indicators:
- **Circuit Breaker Status**: Closed/Open/Half-Open for each agent
- **Checkpoint Management**: List, resume, and manage checkpoints
- **Dead Letter Queue**: View and replay failed tasks
- **Feature Tracking**: Real-time feature completion status

### Uniqueness
Unlike basic logging, this system provides:
- **Visual indicators**: Color-coded status for quick scanning
- **Interactive controls**: Click to view details, replay tasks
- **Historical data**: Track health over time
- **Proactive alerts**: Identify issues before they become critical

---

## 7. Failure Recovery Components

### Checkpoints
**What:** Save pipeline state after each agent completes.

**Purpose:** Allow resuming from where you left off if interrupted.

**When used:** After each agent successfully completes its work.

**Example flow:**
1. Agent runs → creates checkpoint with state
2. Pipeline interrupted (crash, timeout, etc.)
3. Resume pipeline → loads checkpoint → continues from last saved state

### Dead Letter Queue (DLQ)
**What:** Captures tasks that permanently failed after all retry attempts.

**Purpose:** Store failed tasks for review and potential replay.

**When used:** After all retry attempts are exhausted.

**Example flow:**
1. Agent fails → retries with fallback models
2. All retries fail → task goes to DLQ
3. Review DLQ → fix issue → replay task

### Circuit Breakers
**What:** Prevent cascading failures by stopping attempts when an agent is broken.

**Purpose:** Stop wasting resources on a failing agent.

**When used:** After 5 consecutive failures (configurable threshold).

**States:**
- **CLOSED** — Normal operation, failures are counted
- **OPEN** — Agent is broken, all attempts blocked for cooldown period
- **HALF-OPEN** — Testing if agent recovered, allow single probe call

**Example flow:**
1. Agent fails → failures count increments
2. 5+ failures → circuit breaker opens (stops agent)
3. Cooldown period expires → half-open state
4. Probe call succeeds → breaker closes (resume normal operation)

### Summary Table

| Component | Purpose | When Used |
|---|---|---|
| Checkpoints | Resume interrupted pipelines | After each agent completes |
| DLQ | Store permanently failed tasks | After retry exhaustion |
| Circuit Breakers | Stop cascading failures | After 5+ consecutive failures |

---

## 8. Per-Project Model Tiers

### Feature
Different projects can use different model tiers:
- **Recommended**: Best quality (~$2.00/run)
- **Cheap**: Budget-optimized (~$0.47/run)
- **Hybrid**: Quality + cost balance (~$0.90/run)
- **ZenFree**: Zero cost (rate-limited)
- **OpenRouter Free**: Zero cost (rate-limited)

### Uniqueness
Unlike fixed model assignments, this system:
- **Optimizes cost**: Use cheaper models for simple tasks
- **Scales quality**: Use better models for complex reasoning
- **Isolates projects**: One project's model choices don't affect others
- **Enables experimentation**: Test different models per project

---

## 9. Git Integration

### Feature
Automatic git integration:
- **Auto-commit**: Per logical change
- **Conventional Commits**: Standardized commit messages
- **Branch naming**: `pipeline/<project>/<feature>`
- **PR workflows**: Automated pull request creation

### Uniqueness
Unlike manual git operations, this system:
- **Tracks changes**: Links commits to pipeline stages
- **Maintains history**: Full audit trail of changes
- **Enables collaboration**: Multiple developers can work on same project
- **Supports rollback**: Easy reverting of changes

---

## 10. Diagram Generation

### Feature
Professional architecture diagram generation:
- **Multiple formats**: .drawio, .vsdx, .pdf, .pptx, .svg, .png
- **Vendor icons**: Official AWS, Azure, GCP icons
- **Auto-generation**: From architecture spec
- **Presentation-ready**: Visio/PPT quality

### Uniqueness
Unlike basic diagrams, this system:
- **Spec-driven**: Generate from structured JSON specification
- **Vendor-specific**: Use official cloud provider icons
- **Multiple outputs**: Generate all formats from single spec
- **Integration**: Diagrams linked to architecture decisions

---

## 11. Context Compaction

### Feature
Intelligent context management:
- **Compact summaries**: 2-3 page summaries of each stage
- **Information Diet**: Pass only what downstream agents need
- **Lazy loading**: Read specific sections, not entire files
- **Cache management**: Reuse summaries when possible

### Uniqueness
Unlike full context passing, this system:
- **Reduces tokens**: Lower cost per agent invocation
- **Improves speed**: Faster agent execution
- **Maintains quality**: Summaries preserve key decisions
- **Scales better**: Works with large codebases

---

## Comparison with Traditional Pipelines

| Aspect | Traditional Pipeline | Multi-Agent Multi-Project Pipeline |
|--------|---------------------|-----------------------------------|
| **Project Isolation** | Shared configuration | Complete isolation per project |
| **Execution Model** | Sequential all stages | Selective agent execution |
| **Implementation** | Single agent | Specialized sub-agents |
| **Documentation** | Static, manual updates | Living document, auto-updated |
| **Failure Handling** | Basic retry | Circuit breakers, checkpoints, DLQ |
| **Monitoring** | Logs only | Real-time dashboard |
| **Model Management** | Fixed models | Per-project model tiers |
| **Git Integration** | Manual | Automatic with conventions |
| **Diagrams** | Manual creation | Auto-generated from spec |
| **Context Management** | Full file passing | Intelligent compaction |
| **Pipeline Execution** | LLM only | Hybrid (script + LLM) |

---

## Use Cases

### 1. Rapid Prototyping
- Use cheap/free tiers for quick iterations
- Run only necessary agents
- Skip unnecessary stages

### 2. Enterprise Development
- Multiple projects with different requirements
- Per-project model tier optimization
- Comprehensive failure recovery

### 3. Team Collaboration
- Multiple developers working on same project
- Git integration with conventional commits
- Feature tracking with assignment

### 4. Cost Optimization
- Choose model tier per project
- Run only needed agents
- Context compaction reduces token usage

### 5. Quality Assurance
- Specialized sub-agents for each domain
- E2E feature implementation
- Comprehensive testing and validation

---

## 12. Hybrid Pipeline Execution (Script + LLM)

### Architecture
The pipeline uses a hybrid approach to balance speed and flexibility:
- **Deterministic commands** → Python script (fast, no LLM)
- **Agent execution** → LLM via Task() calls (flexible, uses AI)

### Known Limitation
The `/pipeline` command in opencode has a context bleeding issue where the LLM doesn't properly load the command file. This affects all `/pipeline` commands.

### Workaround
Use the Python script directly for deterministic commands, and natural language for agent execution.

### How to Use

#### Deterministic Commands (run via bash)
```bash
python scripts/pipeline.py           # Shows usage
python scripts/pipeline.py list      # Lists projects
python scripts/pipeline.py agents    # Lists agents
python scripts/pipeline.py health    # Shows health status
python scripts/pipeline.py test      # Tests infrastructure
python scripts/pipeline.py checkpoints  # Lists checkpoints
python scripts/pipeline.py dlq       # Shows dead letter queue
```

#### Agent Execution (tell the AI directly)
- "Run the pipeline for: Build a recipe sharing platform"
- "Fix the login validation bug"
- "Continue the interrupted pipeline"
- "Run the architect agent"

### Why This Approach?
1. **Speed**: Deterministic commands run instantly via script
2. **Reliability**: No LLM context bleeding for simple commands
3. **Flexibility**: Agent execution still uses AI for complex tasks
4. **Maintainability**: Script is easy to test and modify

### Script Location
- `scripts/pipeline.py` — Handles all deterministic pipeline commands
- `.opencode/command/pipeline.md` — Routes commands to script or LLM

---

## Summary

The Multi-Agent Multi-Project Pipeline uniquely combines:

1. **Multi-project isolation** with per-project configuration
2. **Selective agent execution** for granular control
3. **Specialized sub-agents** for domain expertise
4. **Living documentation** that updates automatically
5. **Failure recovery components** (checkpoints, DLQ, circuit breakers)
6. **Real-time health monitoring** with interactive dashboard
7. **Per-project model tiers** for cost optimization
8. **Automatic git integration** with conventions
9. **Professional diagram generation** from specifications
10. **Intelligent context management** for efficiency
11. **Hybrid pipeline execution** (script + LLM) for optimal performance

These features make it ideal for teams building multiple software products with AI assistance, providing the flexibility, control, and visibility needed for modern software development.
