# Pipeline Template Specification

## Overview

A PipelineTemplate defines a reusable workflow pattern. It can be used as-is, customized per project, or combined with other templates.

## Template Structure

```json
{
  "id": "content-creation",
  "version": "1.0",
  "name": "Content Creation Pipeline",
  "description": "For creating content: books, articles, social media, videos",
  "type": "dynamic",
  "category": "content",
  
  "stages": {
    "0": {
      "name": "Ideation",
      "agent": "ideation",
      "type": "sequential",
      "depends_on": [],
      "description": "Define goals, audience, output format",
      "knowledge_required": ["ui-ux"],
      "skills_required": [],
      "outputs": ["docs/product-plan.md", "pipeline.json"]
    },
    "1": {
      "name": "Content Processing",
      "type": "swarm",
      "depends_on": ["0"],
      "agents": [
        {
          "id": "content-reader",
          "role": "reader",
          "description": "Reads content from various formats"
        },
        {
          "id": "insight-extractor",
          "role": "analyzer",
          "description": "Extracts key insights and ideas"
        },
        {
          "id": "theme-analyzer",
          "role": "pattern-finder",
          "description": "Identifies themes and patterns"
        }
      ],
      "coordination": {
        "pattern": "producer-consumer",
        "queues": {
          "raw-content": ["content-reader"],
          "extracted-insights": ["insight-extractor"],
          "identified-themes": ["theme-analyzer"]
        },
        "completion": "all-agents-idle"
      },
      "knowledge_required": [],
      "skills_required": ["content-analysis"],
      "outputs": ["docs/insights/", "docs/themes/"]
    },
    "2": {
      "name": "Summary Creation",
      "agent": "summary-creator",
      "type": "sequential",
      "depends_on": ["1"],
      "description": "Create summary from insights and themes",
      "knowledge_required": [],
      "skills_required": ["writing"],
      "outputs": ["docs/summary.md"]
    },
    "3": {
      "name": "Journal Writing",
      "agent": "journal-writer",
      "type": "sequential",
      "depends_on": ["2"],
      "description": "Create journal entries from summary",
      "knowledge_required": [],
      "skills_required": ["writing"],
      "outputs": ["docs/journal.md"]
    },
    "4": {
      "name": "Document",
      "agent": "document",
      "type": "sequential",
      "depends_on": ["3"],
      "description": "Format final output",
      "knowledge_required": [],
      "skills_required": [],
      "outputs": ["docs/final/"]
    }
  },

  "agents": {
    "content-reader": {
      "source": ".opencode/agent/content-reader.md",
      "description": "Reads content from various formats",
      "required": true
    },
    "insight-extractor": {
      "source": ".opencode/agent/insight-extractor.md",
      "description": "Extracts key insights and ideas",
      "required": true
    },
    "theme-analyzer": {
      "source": ".opencode/agent/theme-analyzer.md",
      "description": "Identifies themes and patterns",
      "required": true
    },
    "summary-creator": {
      "source": ".opencode/agent/summary-creator.md",
      "description": "Creates summary from insights",
      "required": true
    },
    "journal-writer": {
      "source": ".opencode/agent/journal-writer.md",
      "description": "Creates journal entries",
      "required": true
    },
    "document": {
      "source": ".opencode/agent/document.md",
      "description": "Formats final output",
      "required": false
    }
  },

  "knowledge_domains": ["book-summarization", "writing", "content-analysis"],
  
  "flow": {
    "type": "dag",
    "description": "Sequential with parallel extract/analyze"
  },

  "compliance": {
    "default_checks": ["file_exists", "content_quality", "audit_updated"],
    "stage_overrides": {}
  },

  "metadata": {
    "author": "ideation-agent",
    "created_at": "2026-09-02T00:00:00Z",
    "updated_at": "2026-09-02T00:00:00Z",
    "tags": ["content", "book", "summary", "journal"],
    "examples": ["book-summary", "article-digest", "research-report"]
  }
}
```

## Template Categories

| Category | Description | Examples |
|----------|-------------|----------|
| `software` | Traditional SDLC | software-sdlc (current) |
| `content` | Content creation/processing | book-summary, social-media, video-production |
| `automation` | Workflow automation | email-automation, data-pipeline, cron-jobs |
| `research` | Research/analysis | market-research, competitor-analysis, tech-evaluation |
| `monitoring` | System monitoring | server-health, app-metrics, security-scanning |
| `swarm` | Multi-agent collaboration | agent-swarm, distributed-processing |
| `hybrid` | Mix of above | ai-assistant, full-stack-content |

## Template Inheritance

Templates can extend other templates:

```json
{
  "id": "book-journal-extended",
  "extends": "content-creation",
  "overrides": {
    "stages.2.agents.summary-creator.config": {
      "style": "reflective",
      "length": "detailed"
    }
  },
  "adds": {
    "stages.5": {
      "name": "Review",
      "agent": "review",
      "depends_on": ["4"]
    }
  }
}
```

## Template Registry

Templates are stored in:
```
pipeline_templates/
├── software-sdlc/
│   ├── template.json
│   └── README.md
├── content-creation/
│   ├── template.json
│   └── README.md
├── book-journal/
│   ├── template.json
│   └── README.md
├── social-media/
│   ├── template.json
│   └── README.md
├── research-analysis/
│   ├── template.json
│   └── README.md
├── monitoring-engine/
│   ├── template.json
│   └── README.md
├── agent-swarm/
│   ├── template.json
│   └── README.md
└── custom/
    └── <user-created>/
        ├── template.json
        └── README.md
```

## Template Selection Logic

When user says `/pipeline new <idea>`:

1. **Analyze the idea** using NLP/keyword matching
2. **Search template registry** for matching templates
3. **Score templates** based on:
   - Category match (software, content, automation, etc.)
   - Keyword overlap (book, summary, social, monitor, etc.)
   - User history (what templates worked before)
4. **Present options** to user:
   - "This looks like a content creation project. Use content-creation template?"
   - "Or choose from: [list of similar templates]"
5. **Apply template** with user's customizations
6. **Save as new template** if user made significant changes
