$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root

docker compose -f docker-compose.bench.yml restart extraction-service | Out-Null
do {
    Start-Sleep 2
    $ids = @(docker compose -f docker-compose.bench.yml ps -q extraction-service)
    $listos = @($ids | Where-Object { (docker inspect -f "{{.State.Health.Status}}" $_) -eq "healthy" })
} until ($ids.Count -gt 0 -and $listos.Count -eq $ids.Count)
Start-Sleep 5
Write-Host "Servicio reiniciado: $($ids.Count) réplicas healthy."