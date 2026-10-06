# Uso: .\tests\stress\run-vegeta-docker.ps1 -Label 11-vegeta-docker -Runs 3
param([string]$Label = "vegeta-docker", [int]$Runs = 3)

$ErrorActionPreference = "Continue"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $root
$out = Join-Path $root "docs\mediciones"
$vegeta = Join-Path $root "tools\vegeta.exe"

# Targets con rutas relativas al volumen y destino dentro de la red de Docker
$targets = Get-Content (Join-Path $root "tests\stress\targets.txt") |
    ForEach-Object { ($_ -replace "http://localhost:8080", "http://traefik") -replace "@tests/stress/", "@/work/" }
$targetsFile = Join-Path $root "results\targets-docker.txt"
New-Item -ItemType Directory -Force (Split-Path $targetsFile) | Out-Null
Set-Content -Path $targetsFile -Value $targets

for ($i = 1; $i -le $Runs; $i++) {
    & "$PSScriptRoot\restart-bench.ps1" | Out-Null
    docker run --rm --network pdf-bench_traefik-net `
        -v "${root}\tests\stress:/work" -v "${root}\results:/res" `
        --entrypoint /bin/sh peterevans/vegeta -c `
        "vegeta attack -rate=50 -duration=30s -timeout=30s -targets=/res/targets-docker.txt -output=/res/$Label-run$i.bin && vegeta report /res/$Label-run$i.bin" |
        Tee-Object -FilePath (Join-Path $out "$Label-run$i.txt") | Select-String "Success|Latencies|Status Codes"
}