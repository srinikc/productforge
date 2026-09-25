#!/bin/bash
# Product Forge - Installation Script for Linux/macOS
# Multi-Agent Multi-Project System

echo "================================================"
echo "Product Forge - Multi-Agent Multi-Project System"
echo "================================================"
echo

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.10 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Install dependencies
echo
echo "Installing dependencies..."
pip3 install fastapi uvicorn pydantic

# Install optional dependencies for PDF
echo
echo "Installing optional dependencies for PDF generation..."
pip3 install weasyprint playwright 2>/dev/null

# Install the package
echo
echo "Installing Product Forge package..."
pip3 install -e .

# Verify installation
echo
echo "Verifying installation..."
if python3 -c "import core.main" 2>/dev/null; then
    echo "  Core modules: OK"
else
    echo "ERROR: Installation verification failed"
    exit 1
fi

echo
echo "================================================"
echo "Installation Complete!"
echo "================================================"
echo
echo "Next steps:"
echo "  1. Start dashboard: productforge dashboard"
echo "  2. Open browser:  http://localhost:3001"
echo "  3. Run pipeline:  productforge run myworld"
echo "  4. Generate docs:  productforge docs"
echo "  5. Run tests:     productforge test"
echo
echo "For help: productforge help"
echo "Documentation: README.md"
