#!/usr/bin/env bash
# Uso: ./tests/stress/run-vegeta.sh [etiqueta]   (RATE, DURATION, TIMEOUT y TARGETS son opcionales)
set -euo pipefail
cd "$(dirname "$0")/../.."

LABEL="${1:-vegeta}"
RATE="${RATE:-50}"
DURATION="${DURATION:-30s}"
TIMEOUT="${TIMEOUT:-30s}"
TARGETS="${TARGETS:-tests/stress/targets.txt}"

mkdir -p results docs/mediciones
BIN_OUTPUT="results/${LABEL}-vegeta.bin"

vegeta attack -rate="${RATE}" -duration="${DURATION}" -timeout="${TIMEOUT}" -targets="${TARGETS}" \
  | tee "${BIN_OUTPUT}" | vegeta report | tee "docs/mediciones/${LABEL}-vegeta.txt"
vegeta report -type=json < "${BIN_OUTPUT}" > "docs/mediciones/${LABEL}-vegeta.json"
vegeta plot < "${BIN_OUTPUT}" > "results/${LABEL}-vegeta.html"