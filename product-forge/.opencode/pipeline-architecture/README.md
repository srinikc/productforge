# Pipeline Architecture Documentation

This directory contains the architecture documentation for the Multi-Agent Pipeline System itself (not per-project).

## Files

### 1. `pipeline-architecture.drawio`
- **Format**: Draw.io diagram file
- **Purpose**: Complete visual architecture diagram showing the overall pipeline system
- **Contents**:
  - All 9 pipeline stages (Ideation through Package)
  - 15+ agents and sub-agents
  - Model tier assignments (7 tiers)
  - Data flow between stages
  - Checkpoint and recovery architecture
  - Artifact catalogs per stage (per-project and pipeline-level)

### 2. `architecture-overview.html`
- **Format**: Self-contained HTML document
- **Purpose**: Text-based architecture overview for the pipeline system
- **Contents**:
  - Pipeline stage descriptions
  - Model tier details and assignments
  - Agent responsibilities and models
  - Artifact flow documentation
  - Configuration schemas

## Generating PDF

```bash
cd .opencode/pipeline-architecture
python generate_pdf.py
```

Or:
1. Open `pipeline-architecture.drawio` in draw.io app
2. File -> Export As -> PDF
3. Save to `pipeline-architecture.pdf`

## What These Files Describe

This is the **pipeline system architecture** - how the multi-agent, multi-project pipeline works.

For **project-specific architecture** (the product being built), see:
- `products/<project>/architecture/` - Project architecture files
- `products/<project>/project-config.json` - Project decisions

## Pipeline Overview

```
9 Stages (0-8):
  0. Ideation      ->  1. Design        ->  2. Architect      ->  3. Review
  4. Implement     ->  5. Validate     ->  6. Fix            ->  7. Document
                                                                        |
                                                                   8. Package

Model Tiers (7):
  - recommended (default) - cheap - hybrid - zenfree - orouterfree
  - premium (NEW) - education (NEW)

Agent Types (15 total):
  Core Agents: ideation, design, architect, review, code-review, validate, fix
  New Agents: document, package
  Implement Sub-Agents: api, db, ui-ux, business-logic
```

Last updated: 2026-08-26