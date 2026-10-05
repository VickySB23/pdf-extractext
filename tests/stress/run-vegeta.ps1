# Uso (desde cualquier carpeta):
#   .\tests\stress\run-vegeta.ps1 -Label 03-baseline-pypdf
param(
    [string]$Label = "baseline",
    [int]$Rate = 50,
    [string]$Duration = "30s",
    [string]$Timeout = "30s"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root

$vegeta  = Join-Path $root "tools\vegeta.exe"
$targets = "tests/stress/targets.txt"

New-Item -ItemType Directory -Force results | Out-Null
$bin  = "results\$Label-vegeta.bin"
$txt  = "docs\mediciones\$Label-vegeta.txt"
$json = "docs\mediciones\$Label-vegeta.json"

& $vegeta attack "-rate=$Rate" "-duration=$Duration" "-timeout=$Timeout" "-targets=$targets" "-output=$bin"
& $vegeta report $bin | Out-File -Encoding utf8 $txt
& $vegeta report "-type=json" $bin | Out-File -Encoding utf8 $json
& $vegeta plot "-output=results\$Label-vegeta.html" $bin

Get-Content $txt