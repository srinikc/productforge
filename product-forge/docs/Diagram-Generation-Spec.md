# Diagram Generation Specification

## Overview

This document specifies how to generate professional architecture diagrams from pipeline artifacts. The goal is to produce Visio/PPT-quality diagrams with official vendor icons, connectors, and flow directions.

## Supported Output Formats

| Format | Tool | Purpose |
|--------|------|---------|
| `.drawio` | archdiagram | Editable in draw.io (free Visio alternative) |
| `.vsdx` | archdiagram | Opens in Microsoft Visio |
| `.pdf` | archdiagram | Presentation-ready with vendor icons |
| `.pptx` | architecture-drawer / PptxGenJS | Editable PowerPoint with native shapes |
| `.svg` / `.png` | diagrams (Python) | Documentation, web embedding |

## Recommended Tools

### Tier 1: Best for Professional Output

1. **diagrams (Python)** - Mature, battle-tested, huge icon library ✅ INSTALLED
2. **OpenFlowKit** - Visual canvas + AI generation + animated export
3. **draw.io CLI** - Official draw.io command-line export

### Tier 2: Good Alternatives

1. **diagrams-js** - TypeScript, browser-based, WebAssembly
2. **spinediagrams** - Clean slide-ready diagrams, zero deps
3. **drawio-mcp-server** - Azure-heavy projects
4. **Figcraft** - 3D shapes, Markdown labels, MCP
5. **Kymostudio** - Animated SVGs, Figma export

### Tier 3: AI-Powered

1. **mcp-diagram-designer** - Pretty presentation images from Mermaid
2. **diagrams.so** - API-driven, Well-Architected review

## Integration into Pipeline

### Stage 2 (Architect Agent)

The architect agent outputs:

1. **docs/architecture.md** - Human-readable architecture document
2. **docs/architecture-spec.json** - Structured spec for diagram generation

#### Architecture Spec Schema

```json
{
  "title": "MyWorld Architecture",
  "direction": "TB",
  "groups": [
    {
      "id": "frontend",
      "label": "Web Frontend",
      "vendor": "generic"
    },
    {
      "id": "backend",
      "label": "Backend API",
      "vendor": "generic"
    },
    {
      "id": "data",
      "label": "Data Layer",
      "vendor": "generic"
    }
  ],
  "nodes": [
    {
      "id": "nextjs",
      "service": "programming.nextjs",
      "label": "Next.js 14",
      "group": "frontend"
    },
    {
      "id": "fastapi",
      "service": "programming.fastapi",
      "label": "FastAPI",
      "group": "backend"
    },
    {
      "id": "postgres",
      "service": "database.postgres",
      "label": "PostgreSQL 16",
      "group": "data"
    },
    {
      "id": "redis",
      "service": "database.redis",
      "label": "Redis 7",
      "group": "data"
    }
  ],
  "edges": [
    {
      "source": "nextjs",
      "target": "fastapi",
      "label": "REST API"
    },
    {
      "source": "fastapi",
      "target": "postgres",
      "label": "SQL"
    },
    {
      "source": "fastapi",
      "target": "redis",
      "label": "Cache"
    }
  ]
}
```

### Stage 4 (Implement Agent)

The implement agent renders diagrams:

```bash
# Generate .drawio
python -m archdiagram.cli render docs/architecture-spec.json --format drawio -o docs/architecture.drawio

# Generate .pdf
python -m archdiagram.cli render docs/architecture-spec.json --format pdf -o docs/architecture.pdf

# Generate .pptx (using architecture-drawer)
python -m architecture_drawer render docs/architecture-description.md -o docs/architecture.pptx
```

## Diagram Types

### 1. Pipeline Flow Diagram

Shows the pipeline stages, agents, and gates.

```json
{
  "title": "Pipeline Flow",
  "direction": "LR",
  "groups": [
    {
      "id": "stages",
      "label": "Pipeline Stages",
      "vendor": "generic"
    }
  ],
  "nodes": [
    { "id": "s0", "service": "process.start", "label": "Stage 0: Ideation", "group": "stages" },
    { "id": "s1", "service": "process.step", "label": "Stage 1: Design", "group": "stages" },
    { "id": "s2", "service": "process.step", "label": "Stage 2: Architect", "group": "stages" },
    { "id": "s3", "service": "process.step", "label": "Stage 3: Review", "group": "stages" },
    { "id": "s4", "service": "process.step", "label": "Stage 4: Implement", "group": "stages" },
    { "id": "s5", "service": "process.step", "label": "Stage 5: Code Review", "group": "stages" },
    { "id": "s6", "service": "process.step", "label": "Stage 6: Validate", "group": "stages" },
    { "id": "s7", "service": "process.end", "label": "Stage 7: Fix Loop", "group": "stages" }
  ],
  "edges": [
    { "source": "s0", "target": "s1", "label": "product-plan.md" },
    { "source": "s1", "target": "s2", "label": "requirements.md + design.md" },
    { "source": "s2", "target": "s3", "label": "architecture.md" },
    { "source": "s3", "target": "s4", "label": "review.md (APPROVED)" },
    { "source": "s4", "target": "s5", "label": "src/" },
    { "source": "s5", "target": "s6", "label": "code-review.md" },
    { "source": "s6", "target": "s7", "label": "issues.md" },
    { "source": "s7", "target": "s6", "label": "fix → revalidate" }
  ]
}
```

### 2. Architecture Diagram

Shows the system architecture with cloud services.

```json
{
  "title": "MyWorld Architecture",
  "direction": "TB",
  "groups": [
    {
      "id": "frontend",
      "label": "Web Frontend",
      "vendor": "aws"
    },
    {
      "id": "backend",
      "label": "Backend Services",
      "vendor": "aws"
    },
    {
      "id": "data",
      "label": "Data Layer",
      "vendor": "aws"
    }
  ],
  "nodes": [
    { "id": "cloudfront", "service": "network.cloudfront", "label": "CloudFront", "group": "frontend" },
    { "id": "s3", "service": "storage.s3", "label": "S3 Static", "group": "frontend" },
    { "id": "alb", "service": "network.elb", "label": "ALB", "group": "backend" },
    { "id": "ecs", "service": "compute.ecs", "label": "ECS Fargate", "group": "backend" },
    { "id": "rds", "service": "database.rds", "label": "RDS PostgreSQL", "group": "data" },
    { "id": "elasticache", "service": "database.elasticache", "label": "ElastiCache Redis", "group": "data" }
  ],
  "edges": [
    { "source": "cloudfront", "target": "s3", "label": "Static Assets" },
    { "source": "cloudfront", "target": "alb", "label": "API Requests" },
    { "source": "alb", "target": "ecs", "label": "Route" },
    { "source": "ecs", "target": "rds", "label": "SQL" },
    { "source": "ecs", "target": "elasticache", "label": "Cache" }
  ]
}
```

### 3. Data Flow Diagram

Shows how data flows through the system.

```json
{
  "title": "Data Flow",
  "direction": "LR",
  "groups": [
    {
      "id": "input",
      "label": "Input Sources",
      "vendor": "generic"
    },
    {
      "id": "processing",
      "label": "Processing",
      "vendor": "generic"
    },
    {
      "id": "output",
      "label": "Output",
      "vendor": "generic"
    }
  ],
  "nodes": [
    { "id": "user", "service": "actor.user", "label": "User", "group": "input" },
    { "id": "api", "service": "interface.api", "label": "API Gateway", "group": "input" },
    { "id": "auth", "service": "security.auth", "label": "Auth Service", "group": "processing" },
    { "id": "business", "service": "process.business", "label": "Business Logic", "group": "processing" },
    { "id": "db", "service": "database.primary", "label": "Database", "group": "processing" },
    { "id": "response", "service": "interface.response", "label": "Response", "group": "output" }
  ],
  "edges": [
    { "source": "user", "target": "api", "label": "Request" },
    { "source": "api", "target": "auth", "label": "Authenticate" },
    { "source": "auth", "target": "business", "label": "Authorized Request" },
    { "source": "business", "target": "db", "label": "Read/Write" },
    { "source": "db", "target": "business", "label": "Data" },
    { "source": "business", "target": "response", "label": "Result" },
    { "source": "response", "target": "user", "label": "Response" }
  ]
}
```

## Agent Prompt Integration

### Architect Agent

Add to architect.md prompt:

```
## Diagram Generation

After writing docs/architecture.md, also output docs/architecture-spec.json with the following structure:

{
  "title": "[Project Name] Architecture",
  "direction": "TB",
  "groups": [...],
  "nodes": [...],
  "edges": [...]
}

Use official vendor icons where possible:
- AWS: aws/ folder in diagrams library
- Azure: azure/ folder in diagrams library
- GCP: gcp/ folder in diagrams library
- Generic: generic/ folder in diagrams library

Also output docs/architecture-description.md with a text description of the architecture for PPT generation.
```

### Implement Agent

Add to implement.md prompt:

```
## Diagram Rendering

After implementing the code, render architecture diagrams:

1. Generate .drawio:
   python -m archdiagram.cli render docs/architecture-spec.json --format drawio -o docs/architecture.drawio

2. Generate .pdf:
   python -m archdiagram.cli render docs/architecture-spec.json --format pdf -o docs/architecture.pdf

3. Generate .pptx (if architecture-description.md exists):
   python -m architecture_drawer render docs/architecture-description.md -o docs/architecture.pptx

Report generated diagrams to user.
```

## Dashboard Integration

The dashboard should show:
1. Generated diagram files in the artifacts section
2. Links to view/download diagrams
3. Diagram generation status

## Installation

### diagrams (Python) ✅

```bash
pip install diagrams
# Also install Graphviz binary:
winget install graphviz
```

### architecture-drawer

```bash
# Clone the repository
git clone https://github.com/Andy1314Chen/architecture-drawer.git

# Install dependencies
cd architecture-drawer
pip install -r requirements.txt
```

### PptxGenJS

```bash
npm install pptxgenjs
```

### diagrams (Python)

```bash
pip install diagrams
```

## Future Enhancements

1. **Animated Diagrams** - Use Kymostudio for animated SVGs
2. **Interactive Diagrams** - Use draw.io for web-based interactive diagrams
3. **AI-Generated Diagrams** - Use mcp-diagram-designer for AI-generated images
4. **Template System** - Create diagram templates for common architectures
5. **Auto-Generation** - Automatically generate diagrams from code analysis
