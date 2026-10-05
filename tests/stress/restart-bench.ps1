$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root

docker compose -f docker-compose.bench.yml restart extraction-service | Out-Null
do {
    Start-Sleep 2
    $h = docker inspect -f "{{.State.Health.Status}}" pdf-bench-extraction-service-1
} until ($h -eq "healthy")
Start-Sleep 5
Write-Host "Servicio reiniciado y healthy."