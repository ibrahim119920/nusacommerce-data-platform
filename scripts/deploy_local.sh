#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
cutoff="${DEMO_CUTOFF:-2026-10-02T00:00:00+00:00}"
docker compose --profile tools build app
docker compose --profile streaming up -d --wait postgres payments kafka
docker compose --profile tools run --rm app bootstrap
docker compose --profile tools run --rm app kafka-produce
docker compose --profile tools run --rm app kafka-consume
docker compose --profile tools run --rm app capstone --cutoff "$cutoff"
docker compose --profile monitoring up -d metrics prometheus
if [[ "${1:-}" == "--with-airflow" ]]; then
    docker compose --profile orchestration build airflow
    docker compose --profile orchestration up -d airflow
fi
echo "Health: http://localhost:8014/health ; Prometheus: http://localhost:9094"
