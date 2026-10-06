# Uso: .\tests\stress\run-k6-docker.ps1 -Label 09-wrr -Runs 3
param([string]$Label = "k6docker", [int]$Runs = 3)

$ErrorActionPreference = "Continue"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $root
$out = Join-Path $root "docs\mediciones"

for ($i = 1; $i -le $Runs; $i++) {
    & "$PSScriptRoot\restart-bench.ps1" | Out-Null
    $json = "$Label-run$i-k6.json"
    docker run --rm --network pdf-bench_traefik-net `
        -v "${root}\tests\stress:/work" -v "${out}:/out" -w /work `
        -e BASE_URL=http://traefik grafana/k6 run --quiet `
        --summary-export "/out/$json" k6-spike.js | Out-Null
    $s = Get-Content (Join-Path $out $json) -Raw | ConvertFrom-Json
    $d = $s.metrics.http_req_duration
    "{0} corrida {1}: {2} peticiones, {3:N2} req/s, error {4:P1}, p50 {5:N2}s, p95 {6:N2}s, max {7:N2}s" -f `
        $Label, $i, $s.metrics.http_reqs.count, $s.metrics.http_reqs.rate,
        $s.metrics.http_req_failed.value, ($d.med / 1000), ($d.'p(95)' / 1000), ($d.max / 1000)
}