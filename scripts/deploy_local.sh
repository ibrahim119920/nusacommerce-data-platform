#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
cutoff="${BATCH_CUTOFF:-2026-10-02T00:00:00+00:00}"
docker compose --profile tools build app
docker compose --profile streaming up -d --wait postgres payments kafka
docker compose --profile tools run --rm app bootstrap
docker compose --profile tools run --rm app kafka-produce
docker compose --profile tools run --rm app kafka-consume
docker compose --profile tools run --rm app run --cutoff "$cutoff"
docker compose --profile monitoring up -d metrics prometheus
airflow_address=""
if [[ "${1:-}" == "--with-airflow" ]]; then
    docker compose --profile orchestration build airflow
    docker compose --profile orchestration up -d airflow
    airflow_address="$(docker compose --profile orchestration port airflow 8080)"
fi
metrics_address="$(docker compose --profile monitoring port metrics 8014)"
prometheus_address="$(docker compose --profile monitoring port prometheus 9090)"
echo "NusaCommerce pipeline completed. Health: http://${metrics_address}/health"
echo "Prometheus: http://${prometheus_address}"
if [[ -n "${airflow_address}" ]]; then
    echo "Airflow: http://${airflow_address}"
fi
