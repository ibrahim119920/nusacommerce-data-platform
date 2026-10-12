# NusaCommerce Data Platform

Pipeline data e-commerce lokal untuk order, pembayaran, dan clickstream.
Menggunakan PostgreSQL, dbt, Kafka, Parquet, Spark, Airflow, dan Prometheus.
Seluruh data dan API pembayaran menggunakan fixture sintetis.

Order dan pembayaran masuk ke landing PostgreSQL, lalu dbt membentuk warehouse
serta mart laporan. Clickstream dikirim melalui Kafka. Data landing juga diekspor
ke Parquet untuk agregasi order dengan Spark.

## Menjalankan proyek

Siapkan Docker dengan Linux containers. Dari PowerShell:

```powershell
Copy-Item .env.example .env
.\scripts\deploy_local.ps1
```

Tambahkan `-WithAirflow` untuk menjalankan scheduler Airflow.

Di Linux atau macOS:

```bash
cp .env.example .env
bash scripts/deploy_local.sh
# Tambahkan --with-airflow untuk menjalankan Airflow.
```

Script membangun image, memuat fixture clickstream, menjalankan pipeline,
lalu menyalakan monitoring. Konfigurasi port tersedia di `.env`.

| Layanan | Alamat lokal |
| --- | --- |
| PostgreSQL | `localhost:55449` |
| Payments API | `http://localhost:8019/payments` |
| Kafka | `localhost:19099` |
| Health dan metrics | `http://localhost:8024/health` dan `/metrics` |
| Prometheus | `http://localhost:9095` |
| Airflow | `http://localhost:8099` |

## Memeriksa hasil

```powershell
docker compose --profile tools run --rm app summary
docker compose --profile tools run --rm app monitor
Invoke-RestMethod http://localhost:8024/health
```

Perintah `batch` menjalankan ingestion, dbt, dan quality check. Perintah `run`
melanjutkannya dengan export Parquet, Spark, dan health check. Keduanya menerima
`--cutoff`; gunakan `2026-10-02T00:00:00+00:00` untuk fixture bawaan.
Kafka diproses oleh script deployment, terpisah dari kedua perintah tersebut.

## Pengujian

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
docker compose up -d postgres
.\scripts\test.ps1
```

Test integrasi memakai database terpisah dengan akhiran `_test`.
Test Spark memerlukan Java 17+, `requirements-spark.txt`, dan `RUN_SPARK_TESTS=1`.
Workflow CI menjalankan pengujian lengkap beserta rekonsiliasi Spark dan warehouse.

Detail alur ada di [arsitektur](docs/architecture.md).
Perintah backfill, retry, dan penghentian layanan ada di [operasi](docs/operations.md).
