# Uso: .\tests\stress\run-vegeta-docker.ps1 -Label 11-vegeta-docker -Runs 3
param([string]$Label = "vegeta-docker", [int]$Runs = 3)

$ErrorActionPreference = "Continue"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $root
$out = Join-Path $root "docs\mediciones"

$targets = Get-Content (Join-Path $root "tests\stress\targets.txt") |
    ForEach-Object { ($_ -replace "http://localhost:8080", "http://traefik") -replace "@tests/stress/", "@/work/" }
$targetsFile = Join-Path $root "results\targets-docker.txt"
New-Item -ItemType Directory -Force (Split-Path $targetsFile) | Out-Null
Set-Content -Path $targetsFile -Value $targets

for ($i = 1; $i -le $Runs; $i++) {
    & "$PSScriptRoot\restart-bench.ps1" | Out-Null

    $stats = Join-Path $out "$Label-run$i-stats.txt"
    if (Test-Path $stats) { Remove-Item $stats }
    $job = Start-Job -ArgumentList $stats -ScriptBlock {
        param($f)
        1..14 | ForEach-Object {
            Get-Date -Format "HH:mm:ss" | Out-File -Append -Encoding utf8 $f
            docker stats --no-stream | Out-File -Append -Encoding utf8 $f
            Start-Sleep 3
        }
    }

    docker run --rm --network pdf-bench_traefik-net `
        -v "${root}\tests\stress:/work" -v "${root}\results:/res" `
        --entrypoint /bin/sh peterevans/vegeta -c `
        "vegeta attack -rate=50 -duration=30s -timeout=30s -targets=/res/targets-docker.txt -output=/res/$Label-run$i.bin && vegeta report /res/$Label-run$i.bin" |
        Tee-Object -FilePath (Join-Path $out "$Label-run$i.txt") | Select-String "Success|Status Codes"

    Wait-Job $job | Out-Null
    Remove-Job $job
}
