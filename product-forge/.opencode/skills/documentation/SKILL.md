# Documentation Agent Skill

## Purpose
Generates comprehensive documentation for the completed software product including README, user guides, API documentation, architecture diagrams, and PDF exports.

## Stage
Stage 7: Document (after Validate → Fix)

## Inputs
- Completed source code from `products/<project>/src/`
- Test reports from `products/<project>/reports/`
- Architecture docs from `products/<project>/architecture/`
- Project config from `products/<project>/project-config.json`
- Design docs from `products/<project>/design/`

## Outputs
- `products/<project>/docs/` - Markdown documentation
  - `README.md` - Project overview, quick start, features
  - `USER_GUIDE.md` - End-user documentation
  - `DEVELOPER_GUIDE.md` - Setup, contribution, architecture
  - `API.md` - REST/GraphQL API reference
  - `ARCHITECTURE.md` - System design, data flow, decisions
  - `DEPLOYMENT.md` - Deployment instructions per platform
  - `CHANGELOG.md` - Version history
  - `CONTRIBUTING.md` - Contribution guidelines
- `products/<project>/docs/pdf/` - PDF exports
  - `README.pdf`
  - `USER_GUIDE.pdf`
  - `API.pdf`
  - `ARCHITECTURE.pdf`
- `products/<project>/docs/openapi/` - OpenAPI/Swagger specs
  - `openapi.json` / `openapi.yaml`
- `products/<project>/docs/diagrams/` - Mermaid diagrams source
  - `architecture.mmd`
  - `data-flow.mmd`
  - `sequence-*.mmd`

## Tools & Libraries

### Core Documentation
- **marked** - Markdown parser/renderer
- **markdown-it** - Extensible markdown parser
- **front-matter** - YAML front matter parsing

### PDF Generation
- **weasyprint** - HTML to PDF (CSS Paged Media)
- **puppeteer** - Headless Chrome for PDF generation
- **pdfkit** - PDF generation from HTML (requires wkhtmltopdf)

### API Documentation
- **swagger-jsdoc** - JSDoc to OpenAPI
- **swagger-ui-dist** - Interactive API docs
- **redoc** - Alternative API reference UI

### Diagram Generation
- **mermaid** - Diagram generation (flow, sequence, class, ER)
- **mermaid-cli** - CLI for Mermaid to SVG/PNG/PDF
- **@mermaid-js/mermaid-cli** - Official CLI

### Code Analysis
- **scancode-toolkit** - License, copyright, package detection
- **typedoc** - TypeScript API documentation
- **jsdoc** - JavaScript API documentation

## Workflow

### 1. Discovery Phase
- Scan `project-config.json` for project metadata
- Analyze source code structure in `src/`
- Read existing architecture/design docs
- Identify API endpoints from code

### 2. Content Generation
- **README.md**: Project name, description, badges, quick start, features, links
- **USER_GUIDE.md**: Screenshots, workflows, troubleshooting, FAQ
- **DEVELOPER_GUIDE.md**: Prerequisites, setup, scripts, testing, debugging
- **API.md**: Endpoints, schemas, auth, examples, error codes
- **ARCHITECTURE.md**: System context, containers, components, data flow, decisions
- **DEPLOYMENT.md**: Docker, cloud, mobile, desktop, CI/CD
- **CHANGELOG.md**: From git history or manual entries
- **CONTRIBUTING.md**: Code style, PR process, issue templates

### 3. API Spec Generation
- Parse route handlers for OpenAPI spec
- Extract schemas from validation/DTOs
- Generate `openapi.json` and `openapi.yaml`

### 4. Diagram Generation
- Create Mermaid diagrams for:
  - System architecture (C4 context/container)
  - Data flow diagrams
  - Key sequence diagrams
  - Database ER diagram
- Export to SVG/PNG for embedding

### 5. PDF Export
- Convert each Markdown file to HTML with styling
- Generate PDF via WeasyPrint or Puppeteer
- Apply consistent headers/footers, TOC, page numbers
- A4 portrait for docs, A3 landscape for architecture

### 6. Validation
- Check all links work (internal/external)
- Verify code examples compile/run
- Validate OpenAPI spec
- Ensure PDFs render correctly

## Configuration
```json
{
  "documentation": {
    "includeApiDocs": true,
    "includeUserGuide": true,
    "includeArchitecture": true,
    "pdfEngine": "weasyprint",  // or "puppeteer", "pdfkit"
    "outputFormats": ["md", "pdf", "html"],
    "theme": "github",  // or "gitbook", "readthedocs"
    "logoPath": "assets/logo.png",
    "faviconPath": "assets/favicon.ico"
  }
}
```

## Model Assignment
- **Model Tier**: Uses project's model tier (from project-config.json)
- **Recommended**: Hybrid or Recommended tier for quality docs
- **Fallback**: Cheap tier acceptable for basic README

## Quality Checks
- [ ] All markdown files render without errors
- [ ] All internal links resolve
- [ ] Code examples are syntactically correct
- [ ] OpenAPI spec passes validation
- [ ] PDFs generate without missing fonts/images
- [ ] Diagrams render correctly
- [ ] No TODOs or placeholder content remains

## Error Handling
- Missing source files → Log warning, generate skeleton
- PDF generation fails → Fall back to HTML output
- API parsing fails → Document manually from routes
- Diagram rendering fails → Include source .mmd files

## Integration Points
- Reads from: `project-config.json`, `src/`, `reports/`, `architecture/`, `design/`
- Writes to: `docs/`, `docs/pdf/`, `docs/openapi/`, `docs/diagrams/`
- Triggers: After Stage 6 (Fix) completes successfully
- Next: Stage 8 (Package) consumes docs for packaging