# NusaCommerce Data Platform

Project e-commerce sintetis untuk portfolio internship Data Engineering: ingestion → warehouse → orchestration → quality/monitoring → local deployment → documentation, ditambah Kafka, Parquet dan Spark. Dikembangkan sebagai capstone course 14 hari dengan bantuan mentor/AI.

Version saat ini 0.14.0. Implementasi ini berasal dari copy reference capstone; folder latihan lokal asli tetap terpisah. Nama project Compose `nusacommerce_reference9` dipertahankan agar volume demo lama tetap dapat digunakan. Ini project pembelajaran yang dapat direproduksi, bukan klaim sistem production-ready.

## Quickstart: deployment lokal

Dari root folder ini, gunakan Docker Desktop (Linux containers, AMD64) dan PowerShell:

```powershell
.\scripts\deploy_local.ps1
# Untuk menambahkan Airflow:
.\scripts\deploy_local.ps1 -WithAirflow
```

Linux:

```bash
bash scripts/deploy_local.sh
bash scripts/deploy_local.sh --with-airflow
```

Build pertama mengunduh Java, PySpark dan dependencies; sediakan waktu dan ruang disk. Tidak perlu Java di Windows untuk jalur Docker. Script menjalankan PostgreSQL, mock payments dan Kafka, memuat events, membangun warehouse/lake/Spark, lalu menyalakan monitoring. Airflow optional menggunakan runtime terpisah.

Jangan menjalankan mock API Python lokal bersamaan dengan payments Docker: keduanya memakai port 8009. Jika ada port conflict, sesuaikan root Compose. Credential contoh hanya untuk localhost.

| Komponen | Akses |
|---|---|
| PostgreSQL | localhost:55439 |
| Mock payments | http://localhost:8009/payments |
| Health / metrics | http://localhost:8014/health dan /metrics |
| Prometheus / alerts | http://localhost:9094 |
| Airflow optional | http://localhost:8089 |
| Kafka external | localhost:19099 |

Airflow memakai standalone + metadata SQLite dan semua akses localhost sebagai admin; jangan diekspos ke internet. Prometheus alert rules menampilkan pending/firing tetapi belum mengirim email/Slack.

## Menjalankan dan memeriksa hasil

```powershell
docker compose --profile tools run --rm app summary
docker compose --profile tools run --rm app monitor
Invoke-RestMethod http://localhost:8014/health
# Ulang end-to-end (snapshot baru, raw tetap idempotent):
docker compose --profile tools run --rm app capstone --cutoff '2026-10-02T00:00:00+00:00'
```

Fixture memiliki tanggal tetap. Cutoff tidak boleh mundur dari checkpoint yang sudah sukses; setelah memakai cutoff lebih baru, gunakan cutoff sama/lebih baru atau backfill. CLI capstone tidak menyalakan Kafka; deployment script menjalankan producer/consumer terlebih dahulu.

Expected fixture: 8 raw order versions, 6 payments, 6 clickstream events, 1 refund. Finance: revenue IDR 1.345.000, refund IDR 25.000, net IDR 1.320.000. Hari hanya refund dapat mempunyai net negatif.

Spark daily orders (order created date, berbeda dari payment date): 2026-09-27 = 3 orders / IDR 464.000; 2026-09-28 = 4 orders / IDR 881.000. Latest cancelled order dikeluarkan setelah dedup.

Data lake: named volume reference_artifacts di /opt/nusa-project/artifacts/lake. Setiap export membuat snapshot baru dengan manifest/checksum; derived output berada di derived/<snapshot_id>/<run_id>/. Untuk melihat pointer:

```powershell
docker compose --profile tools run --rm --entrypoint /bin/sh app -c 'cat /opt/nusa-project/artifacts/lake/latest.json'
```

Tidak ada retention otomatis: full snapshots bertambah tiap run.

## Arsitektur singkat

```text
Orders DB ──window/keyset────┐
Payments API ──retry/pages──┼──> PostgreSQL raw ──> dbt facts/dims ──> marts
Clickstream ──Kafka/sink────┘          |
                               Parquet snapshot ──> Spark batch ──> derived output

Airflow: bootstrap → [orders,payments] → warehouse → quality → lake → spark → monitor
Exporter → Prometheus + alert rules
CI + reconciliation → manual image publish → local deployment
```

Kafka consumer melakukan DB commit sebelum offset commit: at-least-once dengan idempotent sink, bukan exactly-once lintas dua sistem. Spark local[2] adalah single-machine demo, bukan cluster multi-host.

## Airflow

```powershell
docker compose --profile orchestration build airflow
docker compose --profile orchestration up -d airflow
docker compose --profile orchestration exec airflow airflow dags list-import-errors
docker compose --profile orchestration exec airflow airflow dags test nusacommerce_batch 2026-10-02
```

Build app image dahulu (quickstart sudah melakukannya). DAG memakai 8 tasks dan mem-pin snapshot ID lewat XCom. Task logic berada di package Python, tidak ditumpuk dalam file DAG. Scheduled runs memakai data_interval_end sebagai cutoff; demo dag test berbeda dari bukti scheduling 24/7.

## Python lokal: tests dan ingestion tanpa Spark

Python 3.11:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
docker compose up -d postgres
.\scripts\verify_reference.ps1
.\.venv\Scripts\ruff.exe check src tests scripts dags
```

Tanpa Java/PySpark, tiga Spark tests sengaja skipped. Jangan laporkan skips sebagai pass. Untuk Spark lokal Linux, install requirements-spark.txt dan Java 17; set RUN_SPARK_TESTS=1. Jalur Docker sudah menyediakan keduanya.

CI-equivalent lengkap tersedia di scripts/ci_verify.py: butuh dua DB terpisah, POSTGRES_URL untuk demo/CI, TEST_POSTGRES_URL berakhiran _test, dan DBT_* yang menunjuk DB demo. Script menjalankan tests, capstone dan parity Spark-vs-warehouse. Tests hanya mengosongkan *_test, bukan demo.

Python tidak otomatis membaca .env; Compose membacanya, Python memerlukan exported environment. Default helper tests memakai credential lokal; jika diubah, konfigurasi test DB secara manual. Mengubah .env tidak mengubah password PostgreSQL pada volume yang sudah diinisialisasi.

## Recovery dan replay

```powershell
docker compose --profile tools run --rm app backfill --start '2026-09-28T00:00:00+07:00' --cutoff '2026-09-29T00:00:00+07:00'
docker compose --profile tools run --rm app dbt
docker compose --profile tools run --rm app quality
# Replay fixture clickstream:
docker compose --profile tools run --rm app kafka-produce
docker compose --profile tools run --rm app kafka-consume
```

Backfill tidak memundurkan checkpoint. Replay existing events: received 6 / inserted 0 / duplicates 6. Raw/checkpoint tidak boleh dihapus untuk retry. Conflict same ID/version dengan payload berbeda harus diperiksa, bukan silently skip.

Lihat landing.ingestion_runs, control.ingestion_checkpoints, quality.order_conflicts dan control.quality_runs. [Runbook](docs/operations/runbook.md) menjelaskan failure/recovery.

## CI/CD dan GitHub

.github/workflows/ci.yml: unit/integration + actual Spark + capstone/parity + lint/compile + Docker build. publish.yml hanya workflow_dispatch, menunggu reusable CI dan menerbitkan image ber-tag commit SHA ke GHCR.

Status hosted CI dapat diperiksa pada [GitHub Actions](https://github.com/ibrahim119920/nusacommerce-data-platform/actions). Keberhasilan pengujian lokal tidak otomatis membuktikan hosted CI berhasil; jangan tampilkan badge green sebelum workflow sungguh lulus. Workflow release tidak dijalankan otomatis: image publish memerlukan manual dispatch. Local deployment menjadi jalur CD demo; cloud/SSH deployment tidak dijalankan.

Direct dependencies dipin untuk reference, bukan full hash lock/security-audited dependencies. Wheel package bukan distribusi standalone pipeline assets; gunakan checkout editable atau container image. File rahasia, virtual environment, cache dan hasil runtime tidak disertakan dalam Git.

## Struktur dan dokumentasi

```text
src/nusacommerce/
  domain/          kontrak data
  ingestion/       orders + payments
  streaming/       Kafka producer/sink
  lake/            Parquet publisher + Spark job
  monitoring.py    health + Prometheus exporter
  platform.py      bootstrap dan quality
  cli.py           entry point
sql/               migrations + fixture seeds
dbt/               staging, dimensions, facts, marts, data tests
dags/              orchestration capstone
infra/             app/Airflow Dockerfiles, Kafka, Prometheus
scripts/           mock API, tests, CI-equivalent, deployment
tests/             domain/API/transaction/lake/monitoring/Spark
.github/workflows/ CI + manual image release
docs/              architecture, ADR, course mapping, runbook, portfolio
```

- [Hari 1–9](docs/day-01-through-09.md) dan [Hari 10–14](docs/day-10-through-14.md)
- [Arsitektur Hari 14](docs/architecture/reference-day14.md)
- [ADR capstone](docs/adr/0004-capstone-day14.md)
- [Verification terbaru](docs/VERIFICATION.md), [verification historis Hari 9](docs/verification-day09.md)
- [Cloud design, belum dideploy](docs/deployment/cloud-design.md)
- [Portfolio dan interview guide](docs/portfolio/guide.md)

Dokumen dan infra/docker lama adalah histori latihan. Untuk reference terbaru, gunakan compose.yaml di root.

## Batasan jujur

Sources sintetis; customer history/items/products/refunds disediakan seed, bukan CDC. dbt rebuild tables; failure quality tidak membatalkan semua model yang sudah dipublikasikan. Orders hanya observed current-state versions dengan lookback 15 menit. Full-snapshot exporter mengambil tables ke memory. Kafka satu broker ephemeral; Airflow standalone. Tidak ada managed cloud, HA, notification delivery, atau soak/load test produksi.

## Stop tanpa menghapus data

```powershell
docker compose --profile streaming --profile monitoring --profile orchestration stop
```

Jangan memakai down -v bila ingin mempertahankan PostgreSQL dan Parquet demo.
