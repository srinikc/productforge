# Multi-Agent Multi-Project Pipeline Architecture

## Overview

An 8-stage AI-powered pipeline that transforms product ideas into working code through structured agent workflows.

## Pipeline Flow

```
User Input → Ideation → Design → Architect → Review → Gate → Implement → Code Review → Validate → Fix Loop → Done
```

## Stages

### Stage 0: Ideation
- **Model**: mimo-v2.5
- **Cost**: ~$0.02
- **Input**: Idea (text or file)
- **Output**: product-plan.md
- **Process**: Summarize → Confirm → Agent Meeting → Optional Requirements

### Stage 1: Design
- **Model**: minimax-m3
- **Cost**: ~$0.04
- **Input**: product-plan.md
- **Output**: requirements.md + design.md
- **Process**: User stories, acceptance criteria, component design

### Stage 2: Architect
- **Model**: qwen3.7-max
- **Cost**: ~$0.53
- **Input**: requirements.md + design.md
- **Output**: architecture.md + architecture.d2
- **Process**: Tech stack, ADRs, system design

### Stage 3: Review
- **Model**: qwen3.7-plus
- **Cost**: ~$0.07
- **Input**: architecture.md
- **Output**: review.md (MUST contain APPROVED)
- **Process**: Quality gate, feasibility check

### Gate: Approved?
- **Rule**: review.md MUST contain APPROVED
- **APPROVED**: Proceed to Implement
- **CHANGES**: Return to Review

### Stage 4: Implement
- **Model**: kimi-k2.7-code
- **Cost**: ~$0.62
- **Input**: architecture.md + design.md
- **Output**: src/ (production code)
- **Process**: Code generation, tests

### Stage 5: Code Review
- **Model**: kimi-k2.7-code
- **Cost**: ~$0.37
- **Input**: src/
- **Output**: code-review.md
- **Process**: Quality, security, performance review

### Stage 6: Validate
- **Model**: deepseek-v4-flash
- **Cost**: ~$0.04
- **Input**: src/ + code-review.md
- **Output**: issues.md
- **Process**: Run tests, check issues

### Stage 7: Fix
- **Model**: kimi-k2.7-code
- **Cost**: ~$0.31
- **Input**: issues.md
- **Output**: Updated src/
- **Process**: Fix issues, loop back to Validate

## Recovery Components

### Checkpoints
- Save state after each agent
- Enable resume from any stage

### Dead Letter Queue (DLQ)
- Store failed tasks
- Manual review and retry

### Circuit Breakers
- 5+ failures = OPEN
- Prevent cascade failures

## Model Tiers

| Tier | Cost/Run | Best For |
|------|----------|----------|
| Recommended | ~$2.00 | Full quality |
| Cheap | ~$0.47 | Budget |
| Hybrid | ~$0.90 | Balance |
| ZenFree | $0 | Testing |

## Artifacts

| Artifact | Stage | Description |
|----------|-------|-------------|
| product-plan.md | 0 | Summary + MUST-HAVE + OPTIONAL |
| requirements.md | 1 | User stories + AC |
| design.md | 1 | Component design |
| architecture.md | 2 | Tech stack + ADRs |
| architecture.d2 | 2 | D2 diagram |
| review.md | 3 | APPROVED gate |
| src/ | 4 | Production code |
| code-review.md | 5 | Findings |
| issues.md | 6 | Test failures |
