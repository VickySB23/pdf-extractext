# Uso: .\tests\stress\run-experiment.ps1 -Label 06-maxconc2
param([Parameter(Mandatory = $true)][string]$Label)

$ErrorActionPreference = "Continue"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root
$out = Join-Path $root "docs\mediciones"

function Start-Stats([string]$file) {
    if (Test-Path $file) { Remove-Item $file }
    Start-Job -ArgumentList $file -ScriptBlock {
        param($f)
        1..14 | ForEach-Object {
            Get-Date -Format "HH:mm:ss" | Out-File -Append -Encoding utf8 $f
            docker stats --no-stream | Out-File -Append -Encoding utf8 $f
            Start-Sleep 5
        }
    }
}

& "$PSScriptRoot\restart-bench.ps1"
$cfg = Join-Path $out "$Label-config.txt"
docker compose -f docker-compose.yml logs extraction-service |
    Select-String "MAX_CONCURRENT" | Select-Object -Last 1 | Out-File -Encoding utf8 $cfg
Get-Content $cfg

$job = Start-Stats (Join-Path $out "$Label-k6-stats.txt")
k6 run --summary-export (Join-Path $out "$Label-k6.json") tests\stress\k6-spike.js
Wait-Job $job | Out-Null
Remove-Job $job

Start-Sleep 15

& "$PSScriptRoot\restart-bench.ps1"
$job = Start-Stats (Join-Path $out "$Label-vegeta-stats.txt")
& "$PSScriptRoot\run-vegeta.ps1" -Label $Label
Wait-Job $job | Out-Null
Remove-Job $job

Write-Host "Listo. Resultados en docs\mediciones\$Label-*"
