# Product Forge

**Multi-Agent Multi-Project System**

A comprehensive pipeline orchestration system with 17 specialized agents, workflow documentation, PDF generation, and a modern dashboard interface.

## Features

- **17 Specialized Agents**: Ideation, Design, Architect, Security, Implement, Code Review, Validate, Document, Package, DevOps, Customer Onboarding, Marketing, Presentation, Maintenance, FinOps, Domain Research, Product Analyzer
- **Workflow Documentation**: Auto-generated HTML, Draw.io diagrams, and PDF for pipeline and all agents
- **Modern Dashboard**: Real-time monitoring with Simple/Advanced mode toggle
- **Multi-Project Support**: Manage multiple projects from a single dashboard
- **Security Scanning**: Built-in SAST, DAST, secret detection, and dependency scanning
- **Cost Management**: FinOps integration with budget tracking and optimization
- **Quality Assurance**: Comprehensive testing strategy with >80% coverage

## Quick Start

### Installation

```bash
# Navigate to the product-forge directory
cd product-forge

# Install the package
pip install -e .
```

### Running the Dashboard

```bash
# Using the CLI
productforge dashboard

# OR using Python directly
python core/main.py dashboard

# OR start the server directly
python pipeline_dashboard/serve.py
```

Then open your browser to: http://localhost:3001

### Running a Pipeline

```bash
# Run pipeline for a product
productforge run myworld

# Run in simple mode (reduced complexity)
productforge run myworld --simple
```

### Generate Documentation

```bash
# Generate all workflow documentation
productforge docs
```

### List Products

```bash
# See all available products
productforge list
```

## Project Structure

```
product-forge/
├── core/                    # Core Python modules (17 files)
│   ├── workflow_docs.py    # Documentation generator
│   ├── pdf_generator.py    # PDF generation
│   ├── main.py            # CLI entry point
│   ├── lock_manager.py    # Concurrency control
│   ├── state_machine.py   # State management
│   ├── security/         # Security scanning modules
│   └── [13 more modules] # And more...
│
├── pipeline_dashboard/     # Dashboard UI and server
│   ├── index.html        # Main dashboard
│   ├── serve.py          # HTTP server
│   └── docs/            # Generated documentation
│
├── products/              # Product definitions
├── test-framework/       # Test suite (371 tests)
├── scripts/             # Pipeline scripts
└── setup.py            # Package configuration
```

## Dashboard Features

When you start the dashboard (http://localhost:3001), you'll see:

- **Product Forge Branding**: "Product Forge - Multi Agent Multi Project System"
- **Simple/Advanced Mode**: Toggle between simplified and full views
- **Workflow Documentation**: View PDFs, HTML, and Draw.io diagrams
- **Real-time Status**: Live pipeline monitoring
- **Multi-Project View**: Manage all products in one place
- **Agent Performance**: Track each agent's progress
- **Security Dashboard**: View security scan results
- **Health Monitoring**: Circuit breakers, checkpoints, DLQ

## CLI Commands

| Command | Description |
|---------|-------------|
| `productforge list` | List all products |
| `productforge run <product>` | Run pipeline for a product |
| `productforge docs` | Generate workflow documentation |
| `productforge dashboard` | Start the dashboard server |
| `productforge test` | Run the test suite |
| `productforge help` | Show help message |

## Documentation

After running `productforge docs`, you'll find generated files in `pipeline_dashboard/docs/`:

- **Pipeline Documentation**:
  - `pipeline-workflow.html` - Full pipeline diagram
  - `pipeline-workflow.drawio` - Draw.io format
  - `pipeline-workflow.pdf` - Printable PDF

- **Agent Documentation** (17 agents):
  - `agent-<name>.html` - Agent workflow details
  - `agent-<name>.drawio` - Draw.io diagram
  - `agent-<name>.pdf` - Printable PDF

## Testing

```bash
# Run all tests
productforge test

# OR run directly with pytest
pytest test-framework/tests/ -v

# Run specific test file
pytest test-framework/tests/pipeline/test_workflow_docs.py -v
```

**Current Status**: 371 tests passing

## System Requirements

- Python 3.10 or higher
- Windows/Linux/macOS compatible
- 4GB RAM minimum
- Internet connection for initial setup

## Dependencies

Core dependencies (automatically installed):
- FastAPI (web framework)
- Pydantic (data validation)
- uvicorn (ASGI server)

Optional dependencies (for enhanced features):
- weasyprint (PDF generation)
- playwright (browser automation)
- pdfkit (PDF generation)

## Configuration

### Products

Products are defined in the `products/` directory. Each product has:
- `project-config.json` - Project configuration
- `docs/` - Documentation files
- `pipeline-state.md` - Pipeline state tracking

### Environment Variables

```bash
# Optional: Set API keys if needed
export OPENAI_API_KEY=your-key
export GITHUB_TOKEN=your-token
```

## Development

### Running in Development Mode

```bash
# Install in development mode
pip install -e .[dev]

# Run with auto-reload
python pipeline_dashboard/serve.py --reload
```

### Running Tests

```bash
# Run all tests
pytest test-framework/tests/

# Run with coverage
pytest test-framework/tests/ --cov=core --cov-report=html

# Run specific test category
pytest test-framework/tests/pipeline/ -v
```

## Troubleshooting

### Dashboard won't start?

```bash
# Check if port 3001 is available
netstat -an | grep 3001

# Try a different port
python pipeline_dashboard/serve.py --port 3002
```

### PDF generation not working?

Install optional dependencies:

```bash
# Option 1: WeasyPrint (recommended)
pip install weasyprint

# Option 2: PDFKit (requires wkhtmltopdf)
pip install pdfkit
# Also install: https://wkhtmltopdf.org/downloads.html

# Option 3: Playwright
pip install playwright
playwright install chromium
```

### Tests failing?

```bash
# Ensure all dependencies are installed
pip install -e .

# Run tests with verbose output
pytest test-framework/tests/ -vv --tb=long
```

## License

MIT License - See LICENSE file for details

## Support

For issues and questions:
1. Check the documentation in `pipeline_dashboard/docs/`
2. Run `productforge help` for CLI usage
3. Review test examples in `test-framework/tests/`

## Version

**Current Version**: 2.0.0

## Credits

Built with the following technologies:
- Python 3.10+
- FastAPI
- Pydantic
- Uvicorn
- pytest
- And many more...

---

**Product Forge** - Multi-Agent Multi-Project System
