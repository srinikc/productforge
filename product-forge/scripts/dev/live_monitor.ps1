param(
    [int]$Seconds = 30,
    [string]$Log = "products\test-pipeline\pipeline-run.log"
)

$seenFile = "$Log.seen"
$seen = 0
if (Test-Path $seenFile) {
    try { $seen = [int](Get-Content $seenFile -Raw) } catch { $seen = 0 }
}
if (-not (Test-Path $Log)) {
    Write-Output "(waiting for log file $Log ...)"
    Start-Sleep -Seconds 2
}

$deadline = (Get-Date).AddSeconds($Seconds)
while ((Get-Date) -lt $deadline) {
    $lines = @(Get-Content $Log -ErrorAction SilentlyContinue)
    if ($lines.Count -gt $seen) {
        for ($i = $seen; $i -lt $lines.Count; $i++) {
            Write-Output $lines[$i]
        }
        $seen = $lines.Count
        Set-Content -Path $seenFile -Value $seen -Encoding ascii
    }
    Start-Sleep -Seconds 2
}
