# Export Draw.io Diagrams to PDF/PNG
# Usage: .\export-diagrams.ps1 [-InputFile <path>] [-OutputDir <path>]

param(
    [string]$InputFile = "docs\pipeline.drawio",
    [string]$OutputDir = "docs",
    [switch]$All
)

$ErrorActionPreference = "Stop"

# Set Chrome path for Puppeteer
$env:PUPPETEER_EXECUTABLE_PATH = "C:\Program Files\Google\Chrome\Application\chrome.exe"

# Check if drawio CLI is available
if (-not (Get-Command "drawio" -ErrorAction SilentlyContinue)) {
    Write-Error "Draw.io CLI not found. Install: npm install -g draw.io-export"
    exit 1
}

# Export function
function Export-Drawio {
    param(
        [string]$Source,
        [string]$OutputPath,
        [string]$Format
    )
    
    $outputFile = Join-Path $OutputPath ([System.IO.Path]::GetFileNameWithoutExtension($Source) + ".$Format")
    
    Write-Host "Exporting: $Source -> $outputFile" -ForegroundColor Cyan
    
    switch ($Format) {
        "pdf" {
            drawio --export --format pdf --crop --embed-diagram $Source -o $outputFile
        }
        "png" {
            drawio --export --format png --bg white --scale 2 $Source -o $outputFile
        }
        "svg" {
            drawio --export --format svg $Source -o $outputFile
        }
    }
    
    if (Test-Path $outputFile) {
        $size = (Get-Item $outputFile).Length
        Write-Host "  OK: $([math]::Round($size/1KB)) KB" -ForegroundColor Green
    } else {
        Write-Host "  FAILED" -ForegroundColor Red
    }
}

# Main
if ($All) {
    # Export all .drawio files
    $files = Get-ChildItem -Path "docs" -Filter "*.drawio" -Recurse
    foreach ($file in $files) {
        Export-Drawio -Source $file.FullName -OutputPath $OutputDir -Format "pdf"
        Export-Drawio -Source $file.FullName -OutputPath $OutputDir -Format "png"
    }
} else {
    # Export single file
    if (-not (Test-Path $InputFile)) {
        Write-Error "File not found: $InputFile"
        exit 1
    }
    
    Export-Drawio -Source $InputFile -OutputPath $OutputDir -Format "pdf"
    Export-Drawio -Source $InputFile -OutputPath $OutputDir -Format "png"
}

Write-Host "`nDone!" -ForegroundColor Green
