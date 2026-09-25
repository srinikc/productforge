# Pipeline Quick Reference Card

## E2E Flow at a Glance

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              USER INPUT                                         │
│                    (New Idea / Change / Fix)                                    │
└───────────────────────────┬─────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    STAGE 0: IDEATION (Orchestrator)                             │
│                                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│  │  Accept   │───▶│ Summarize│───▶│ Confirm  │───▶│  Agent   │                  │
│  │  Idea     │    │ & Show   │    │ w/User   │    │  Meeting │                  │
│  └──────────┘    └──────────┘    └──────────┘    └─────┬────┘                  │
│                                                         │                       │
│                                                         ▼                       │
│                                                  ┌──────────┐                  │
│                                                  │ Optional │                  │
│                                                  │ Reqs     │                  │
│                                                  └─────┬────┘                  │
│                                                         │                       │
│                                                         ▼                       │
│                                                  ┌──────────┐                  │
│                                                  │product-  │                  │
│                                                  │plan.md   │                  │
│                                                  └──────────┘                  │
└───────────────────────────┬─────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│              STAGES 1-3: DESIGN & REVIEW                                       │
│                                                                                 │
│  Stage 1          Stage 2              Stage 3                                  │
│  ┌────────┐       ┌────────┐           ┌────────┐                              │
│  │ Design │──────▶│Architect│──────────▶│ Review │                              │
│  │Agent   │       │Agent   │           │Agent   │                              │
│  └───┬────┘       └───┬────┘           └───┬────┘                              │
│      │                │                    │                                    │
│      ▼                ▼                    ▼                                    │
│  requirements.md  architecture.md    review.md                                  │
│  design.md        ADRs               (APPROVED gate)                           │
└───────────────────────────┬─────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│              STAGES 4-7: IMPLEMENTATION & VALIDATION                            │
│                                                                                 │
│  Stage 4          Stage 5              Stage 6              Stage 7             │
│  ┌────────┐       ┌────────┐           ┌────────┐           ┌────────┐         │
│  │Implement│──────▶│Code    │──────────▶│Validate│──────────▶│  Fix   │         │
│  │Agent   │       │Review  │           │Agent   │           │ Agent  │         │
│  └───┬────┘       └───┬────┘           └───┬────┘           └───┬────┘         │
│      │                │                    │                    │               │
│      ▼                ▼                    ▼                    ▼               │
│   src/           code-review.md       issues.md           src/ (fixed)         │
│                                               │                               │
│                                               └──────── loop ──────────────────┘
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Model Tiers

| Tier | Cost/Run | Best For |
|------|----------|----------|
| **Recommended** | ~$2.00 | Full quality, all features |
| **Cheap** | ~$0.47 | Budget-conscious, rapid iteration |
| **Hybrid** | ~$0.90 | Best balance (recommended) |
| **ZenFree** | $0 | Testing, no API key needed |
| **OpenRouter Free** | $0 | Alternative free tier |

## Gates

| Gate | Rule |
|------|------|
| **Implement** | `review.md` MUST contain `APPROVED` |
| **Validate** | Runs real tests, writes evidence to `issues.md` |
| **Fix Loop** | `fix` → `validate` → repeat until `issues.md` empty |
| **Circuit Breaker** | 5+ failures → OPEN → cooldown → HALF-OPEN |

## Recovery

| Component | Purpose |
|-----------|---------|
| **Checkpoints** | Save state after each agent completes |
| **DLQ** | Store permanently failed tasks |
| **Circuit Breakers** | Stop cascading failures |

## Commands

```bash
# Pipeline management
/pipeline new "Build app"          # Start new pipeline
/pipeline continue                 # Resume from last stage
/pipeline fix "bug description"    # Fix specific bug
/pipeline list                     # Show all projects

# Selective execution
/pipeline run design               # Run single agent
/pipeline run design,architect     # Run multiple agents
/pipeline run implement --model X  # Run with model override

# Recovery
/pipeline dlq                      # Show dead letter queue
/pipeline checkpoints              # List checkpoints
/pipeline retry <agent>            # Retry failed agent
/pipeline circuit-reset            # Reset circuit breakers

# Models
/models list                       # See current model per agent
/models recommended                # Switch to recommended tier
/models cheap                      # Switch to cheap tier
/models hybrid                     # Switch to hybrid tier
```

## Files

```
docs/
├── product-plan.md           # Stage 0 output (Summary + MUST-HAVE + OPTIONAL)
├── requirements.md           # Stage 1 output
├── design.md                 # Stage 1 output
├── architecture.md           # Stage 2 output
├── review.md                 # Stage 3 output (APPROVED gate)
├── pipeline-state.md         # Audit log (append-only)
├── pipeline-architecture.md  # This file (E2E diagrams)
└── pipeline-architecture-spec.json  # Diagram generation spec

reports/
├── code-review.md            # Stage 5 output
└── issues.md                 # Stage 6 output (fix loop input)

products/<project>/
├── pipeline.json             # Project config
├── checkpoints/              # Recovery checkpoints
├── selective_runs/           # Selective agent runs
└── dlq/                      # Dead letter queue
```
