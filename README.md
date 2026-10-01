# NusaCommerce Data Platform

Project e-commerce untuk belajar membangun data pipeline dengan Python, PostgreSQL, dbt, Airflow, Kafka, Parquet, Spark, dan Docker. Dataset dan API-nya sintetis. Project ini dibuat sebagai portfolio internship dan dikembangkan sambil mengikuti course Data Engineering.

## Menjalankan project

Perlu Docker Desktop dengan Linux containers. Dari PowerShell di Windows:

```powershell
.\scripts\deploy_local.ps1
```

Untuk menjalankan Airflow juga:

```powershell
.\scripts\deploy_local.ps1 -WithAirflow
```

Di Linux atau macOS:

```bash
bash scripts/deploy_local.sh
bash scripts/deploy_local.sh --with-airflow
```

Saat pertama dijalankan, Docker mengunduh beberapa image dan dependency, termasuk Java dan PySpark. Prosesnya perlu waktu dan ruang disk.

| Service | Alamat lokal |
| --- | --- |
| PostgreSQL | `localhost:55439` |
| Payments API | `http://localhost:8009/payments` |
| Health check dan metrics | `http://localhost:8014/health` dan `/metrics` |
| Prometheus | `http://localhost:9094` |
| Airflow (opsional) | `http://localhost:8089` |
| Kafka | `localhost:19099` |

Semua alamat ini untuk penggunaan lokal. Airflow menggunakan mode standalone dengan akses admin; jangan buka servicenya ke internet. Jangan jalankan mock payments lokal bersamaan dengan versi Docker karena keduanya memakai port 8009.

## Alur data

```text
Orders DB ───────┐
Payments API ────┼──> PostgreSQL ──> dbt warehouse ──> Parquet ──> Spark
Clickstream/Kafka┘                       │
                                         └──> Airflow mengatur batch pipeline

Metrics exporter ──> Prometheus
```

Airflow mengatur delapan task dari ingestion sampai monitoring. Logika pemrosesan ada di Python package, terpisah dari DAG. Kafka sink menyimpan data ke PostgreSQL sebelum melakukan commit offset; karenanya konsumen dapat memproses ulang event, dan sink dibuat idempotent untuk menangani duplikasi.

Spark dijalankan lokal dengan dua worker pada satu mesin. Ini contoh pemrosesan batch, bukan cluster terdistribusi.

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

Dokumentasi tambahan:

- [Arsitektur Hari 14](docs/architecture/reference-day14.md)
- [Catatan course Hari 1–14](docs/day-01-through-09.md) dan [Hari 10–14](docs/day-10-through-14.md)
- [Runbook](docs/operations/runbook.md)
- [Hasil verification](docs/VERIFICATION.md)
- [Panduan portfolio](docs/portfolio/guide.md)
- [Desain cloud](docs/deployment/cloud-design.md) — rancangan saja, belum dideploy

## Batasan

Semua source data berupa fixture sintetis; customer, product, dan refund dimuat dari seed, bukan CDC. Kafka berjalan sebagai satu broker. Snapshot exporter membaca tabel ke memory. Belum ada deployment cloud, high availability, pengiriman notifikasi alert, atau load test.

Untuk menghentikan layanan tanpa menghapus data di volume:

```powershell
docker compose --profile streaming --profile monitoring --profile orchestration stop
```
