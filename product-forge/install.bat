@echo off
REM Product Forge - Installation Script for Windows
REM Multi-Agent Multi-Project System

echo ================================================
echo Product Forge - Multi-Agent Multi-Project System
echo ================================================
echo.

REM Check Python version
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10 or higher from https://python.org
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Python version: %PYTHON_VERSION%

REM Install dependencies
echo.
echo Installing dependencies...
pip install fastapi uvicorn pydantic

REM Install optional dependencies for PDF
echo.
echo Installing optional dependencies for PDF generation...
pip install weasyprint playwright 2>nul

REM Install the package
echo.
echo Installing Product Forge package...
pip install -e .

REM Verify installation
echo.
echo Verifying installation...
python -c "import core.main; print('  Core modules: OK')" 2>nul
if errorlevel 1 (
    echo ERROR: Installation verification failed
    pause
    exit /b 1
)

echo.
echo ================================================
echo Installation Complete!
echo ================================================
echo.
echo Next steps:
echo   1. Start dashboard: productforge dashboard
echo   2. Open browser:  http://localhost:3001
echo   3. Run pipeline:  productforge run myworld
echo   4. Generate docs:  productforge docs
echo   5. Run tests:     productforge test
echo.
echo For help: productforge help
echo Documentation: README.md
echo.
pause
