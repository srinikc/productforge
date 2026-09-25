# Book to Journal Pipeline

## What It Does

Reads a book (or any long-form content), extracts key insights, identifies themes, creates a summary, and generates journal entries.

## Pipeline Flow

```
Stage 0: Ideation (define goals, book source)
    │
    ▼
Stage 1: Content Reading (read book, extract text)
    │
    ├──▶ Stage 2: Insight Extraction (parallel)
    │         │
    │         ▼
    │    [insights.md]
    │
    ├──▶ Stage 3: Theme Analysis (parallel)
    │         │
    │         ▼
    │    [themes.md]
    │
    ▼
Stage 4: Summary Creation (combine insights + themes)
    │
    ▼
Stage 5: Journal Writing (create journal entries)
    │
    ▼
Stage 6: Document (format final output)
```

## Agents

| Agent | Role | Description |
|-------|------|-------------|
| content-reader | Reader | Reads book from txt/pdf/epub |
| insight-extractor | Analyzer | Extracts key insights and quotes |
| theme-analyzer | Pattern-finder | Identifies themes and patterns |
| summary-creator | Writer | Creates executive summary |
| journal-writer | Writer | Creates reflective journal entries |
| document | Formatter | Formats final output |

## Usage

```
/pipeline new Create a journal from the book 'Atomic Habits'
```

## Customization

You can customize:
- Output format (markdown, PDF, etc.)
- Journal style (reflective, analytical, creative)
- Summary length (brief, detailed, comprehensive)
- Theme focus (personal growth, business, relationships, etc.)

## Example Projects

- Atomic Habits journal
- Deep Work digest
- Book of the month club
- Reading challenge tracker
