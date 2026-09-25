# Token Counter Utility - Reads from pipeline.json
# Usage: .\token-counter.ps1 -Agent "design" -InputTokens 1500 -OutputTokens 800 -Project "myworld"

param(
    [Parameter(Mandatory=$true)]
    [string]$Agent,
    
    [int]$InputTokens = 0,
    [int]$OutputTokens = 0,
    
    [Parameter(Mandatory=$true)]
    [ValidateSet("start", "end")]
    [string]$Action,
    
    [string]$Stage = "",
    [string]$Artifact = "",
    [string]$Project = "myworld"
)

$ErrorActionPreference = "Stop"

# Token pricing per 1M tokens
$ModelPricing = @{
    "mimo-v2.5" = @{ Input = 0.14; Output = 0.28 }
    "minimax-m3" = @{ Input = 0.30; Output = 1.20 }
    "qwen3.7-max" = @{ Input = 2.50; Output = 7.50 }
    "qwen3.7-plus" = @{ Input = 0.40; Output = 1.60 }
    "kimi-k2.7-code" = @{ Input = 0.95; Output = 4.00 }
    "deepseek-v4-flash" = @{ Input = 0.22; Output = 0.66 }
    "hy3" = @{ Input = 0.14; Output = 0.58 }
    "muse-spark-1.2-contributor" = @{ Input = 0.0; Output = 0.0 }  # Free tier
    "nemotron-3-ultra" = @{ Input = 0.0; Output = 0.0 }  # Free tier
    "nemotron-3.5-lightning" = @{ Input = 0.0; Output = 0.0 }  # Free tier
    "big-pickle" = @{ Input = 0.0; Output = 0.0 }  # Free tier
}

# Read model from pipeline.json
$PipelineConfig = "products/$Project/pipeline.json"
$Model = "unknown"

if (Test-Path $PipelineConfig) {
    $Config = Get-Content $PipelineConfig -Raw | ConvertFrom-Json
    if ($Config.agents.$Agent) {
        $FullModel = $Config.agents.$Agent.model
        # Extract model name from "opencode/model-name" format
        $Model = $FullModel -replace "^opencode/", ""
    }
}

# Calculate cost
$Cost = 0
if ($Model -ne "unknown" -and $ModelPricing.ContainsKey($Model)) {
    $InputCost = ($InputTokens / 1000000) * $ModelPricing[$Model].Input
    $OutputCost = ($OutputTokens / 1000000) * $ModelPricing[$Model].Output
    $Cost = $InputCost + $OutputCost
}

# Create timestamp
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

# Output JSON for logging
$LogEntry = @{
    timestamp = $Timestamp
    agent = $Agent
    model = $Model
    stage = $Stage
    action = $Action
    input_tokens = $InputTokens
    output_tokens = $OutputTokens
    total_tokens = $InputTokens + $OutputTokens
    cost = [math]::Round($Cost, 4)
    artifact = $Artifact
    project = $Project
}

# Convert to JSON
$Json = $LogEntry | ConvertTo-Json -Compress

# Output to stdout
Write-Output $Json

# Append to audit log
$AuditLog = "docs/token-audit.md"
if (-not (Test-Path $AuditLog)) {
    Set-Content -Path $AuditLog -Value "# Token Audit Log`n`n| Timestamp | Agent | Model | Input | Output | Total | Cost |`n|-----------|-------|-------|-------|--------|-------|------|"
}

$Row = "| $Timestamp | $Agent | $Model | $InputTokens | $OutputTokens | $($InputTokens + $OutputTokens) | `$$([math]::Round($Cost, 4)) |"
Add-Content -Path $AuditLog -Value $Row

Write-Host "Token log: $Agent | $Model | In:$InputTokens Out:$OutputTokens | Cost: `$$([math]::Round($Cost, 4))" -ForegroundColor Cyan
