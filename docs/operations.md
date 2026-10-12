# Operasi lokal

## Status dan log

```powershell
docker compose --profile tools run --rm app monitor
docker compose --profile tools run --rm app summary
docker compose logs --tail 50 postgres payments metrics
docker compose --profile orchestration logs --tail 50 airflow
```

`/health` mengembalikan HTTP 200 saat sehat dan 503 saat ingestion gagal,
checkpoint kedaluwarsa, quality check gagal, atau run tersangkut. Metrik tersedia
di `/metrics`; aturan alert ada di `infra/monitoring/alerts.yml`.

| Masalah | Tindakan |
| --- | --- |
| Order ingestion gagal | Jalankan ulang `orders` dengan cutoff yang sama atau lebih baru. |
| Payload berbeda untuk ID dan versi sama | Periksa kontrak sumber dan `quality.order_conflicts`. |
| Payments API gagal | Pulihkan API, lalu jalankan ulang `payments`. |
| Quality check gagal | Perbaiki sumber atau model, lalu ulangi `dbt` dan `quality`. |
| Export atau Spark gagal | Ulangi export, atau jalankan Spark dengan ID snapshot yang sudah valid. |

## Backfill

```powershell
docker compose --profile tools run --rm app backfill --start '2026-09-28T00:00:00+07:00' --cutoff '2026-09-29T00:00:00+07:00'
docker compose --profile tools run --rm app dbt
docker compose --profile tools run --rm app quality
```

Backfill tidak memundurkan checkpoint dan hanya membaca versi yang masih tersedia
di source. Untuk mengulang Spark pada export tertentu:

```powershell
docker compose --profile tools run --rm app spark-build --snapshot-id <snapshot-id>
```

## Konfigurasi dan penyimpanan

Compose membaca `.env`. Perintah Python langsung membutuhkan environment variable
`POSTGRES_URL` dan `PAYMENT_API_URL`; dbt memakai `DBT_HOST`, `DBT_PORT`, `DBT_USER`,
`DBT_PASSWORD`, dan `DBT_DBNAME`. Sesuaikan juga URL tersebut jika port host berubah.
Port Kafka mengikuti advertised listener di `infra/kafka/server.properties`.

Database, metadata Airflow, dan artifacts memakai volume terpisah. Snapshot bertambah
pada setiap export; retensi belum otomatis. Migrasi yang sudah diterapkan diperiksa
berdasarkan nama dan checksum, sehingga perubahan skema berikutnya perlu migrasi baru.

Untuk menghentikan layanan sambil mempertahankan data:

```powershell
docker compose --profile streaming --profile monitoring --profile orchestration stop
```
