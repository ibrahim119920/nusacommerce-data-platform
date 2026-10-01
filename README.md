# NusaCommerce Data Platform

Project e-commerce untuk belajar membangun data pipeline dengan Python, PostgreSQL, dbt, Airflow, Kafka, Parquet, Spark, dan Docker. Dataset dan API-nya sintetis. 
## Menjalankan project

Project menggunakan Docker Desktop dengan Linux containers. Dari PowerShell di Windows:

```powershell
.\scripts\deploy_local.ps1
```

Untuk menjalankan Airflow:

```powershell
.\scripts\deploy_local.ps1 -WithAirflow
```

Di Linux atau macOS:

```bash
bash scripts/deploy_local.sh
bash scripts/deploy_local.sh --with-airflow
```

Image/dependency:

| Service | Alamat lokal |
| --- | --- |
| PostgreSQL | `localhost:55439` |
| Payments API | `http://localhost:8009/payments` |
| Health check dan metrics | `http://localhost:8014/health` dan `/metrics` |
| Prometheus | `http://localhost:9094` |
| Airflow (opsional) | `http://localhost:8089` |
| Kafka | `localhost:19099` |

## Alur data

```text
Orders DB ───────┐
Payments API ────┼──> PostgreSQL ──> dbt warehouse ──> Parquet ──> Spark
Clickstream/Kafka┘                       │
                                         └──> Airflow mengatur batch pipeline

Metrics exporter ──> Prometheus
```

Airflow mengatur delapan task dari ingestion hingga monitoring. Logika pemrosesan ada di Python package, terpisah dari DAG. Kafka sink menyimpan data ke PostgreSQL sebelum melakukan commit offset; karenanya konsumen dapat memproses ulang event, dan sink dibuat idempotent untuk menangani duplikasi.

Spark dijalankan lokal dengan dua worker.

## Memeriksa hasil

Setelah deployment selesai, beberapa perintah yang bisa dicoba:

```powershell
docker compose --profile tools run --rm app summary
docker compose --profile tools run --rm app monitor
Invoke-RestMethod http://localhost:8014/health
```

Untuk menjalankan pengujian DAG Airflow:

```powershell
docker compose --profile orchestration exec -T airflow airflow dags test nusacommerce_batch 2026-10-02
```

Pengujian lokal terbaru menyelesaikan delapan task dengan status sukses. Pengujian manual ini belum membuktikan jadwal Airflow berjalan terus-menerus.

Untuk menjalankan test Python di Windows, siapkan environment dan PostgreSQL lokal:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
docker compose up -d postgres
.\scripts\verify_reference.ps1
```

Tiga test Spark memerlukan Java dan PySpark; script test Windows akan melewatinya jika keduanya tidak tersedia. Pengujian lengkap beserta Spark dan rekonsiliasi hasil dijalankan oleh workflow GitHub Actions.

## Data contoh

Fixture mencakup delapan versi order, enam pembayaran, enam event clickstream, dan satu refund. Nilai net pembayaran setelah refund adalah IDR 1.320.000. Fixture menggunakan tanggal tetap agar hasilnya mudah dibandingkan saat pipeline dijalankan ulang.

Setiap export membuat snapshot Parquet baru beserta manifest dan checksum. File snapshot disimpan dalam Docker volume. Retensi otomatis belum disiapkan, jadi snapshot akan bertambah setiap kali export dilakukan.

## Struktur project

```text
src/nusacommerce/   logika domain, ingestion, Kafka, lake, Spark, monitoring
sql/                migrasi database dan data fixture
dbt/                staging, warehouse, mart, dan data tests
dags/               DAG Airflow
infra/              Dockerfile, Kafka, dan konfigurasi Prometheus
scripts/             deployment, mock API, dan verification
tests/               unit test dan integration test
docs/                arsitektur, ADR, runbook, dan catatan course
```

Untuk menghentikan layanan tanpa menghapus data di volume:

```powershell
docker compose --profile streaming --profile monitoring --profile orchestration stop
```
