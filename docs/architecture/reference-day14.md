# Capstone architecture — Hari 14

Reference ditingkatkan in-place; nama folder reference-day09 dan nama Compose reference9 dipertahankan supaya path serta volume lama tidak rusak. Ini tidak mengubah repository latihan asli.

```text
source.orders ──keyset/window──> staging ──atomic──> raw orders + checkpoint
Payment REST ──retry/pages───────────────────────> raw payment versions
Customer/products/items/refunds fixture─────────> landing
Clickstream fixture → Kafka → Consumer──────────> landing.clickstream_events
                            DB commit BEFORE offset commit
                                                   |
                                +------------------+--------------------+
                                |                                       |
                              dbt                                REPEATABLE READ
                                |                                  raw snapshot
                      dimensions + facts                                 |
                                |                               Parquet + manifest
                         finance/city marts                     event_date partitions
                                |                                       |
                      quality checks/tests                     Spark window + groupBy
                                |                                       |
                      run status/monitoring                    derived Parquet report

Airflow: bootstrap → [orders,payments] → dbt → quality → lake → spark → monitor
                                                      snapshot_id via XCom
Exporter → Prometheus scrape → alert rules
CI → tests + Spark/warehouse parity + image build → manual GHCR publish → local deploy
```

Kafka demo producer/consumer di luar DAG batch. Spark di sini batch local[2], bukan cluster multi-host. Spark mart adalah order value (excluding latest cancelled orders), berbeda dari cash-based finance mart.

## Hari 10: data lake

Snapshot menyimpan seluruh raw versions yang diamati, bukan hanya latest order. PostgreSQL REPEATABLE READ menyatukan pembacaan orders/payments/events. Arrow memberi tipe Decimal dan timestamp UTC; event_date diambil pada timezone Asia/Jakarta. Snapshot dibuat di direktori sementara dan baru dipublikasikan setelah manifest lengkap. latest.json diganti secara atomic pada filesystem yang sama.

Manifest memiliki row count, ukuran dan SHA-256 per file. Reader memvalidasi sebelum memproses. Snapshot ID dan relative path divalidasi untuk mencegah traversal. Snapshot kosong orders ditolak; payments/clickstream kosong tetap mempunyai Parquet schema.

Model ini bukan Delta/Iceberg/Hudi: tidak ada transaksi tabel, compaction terjadwal, schema registry, atau version vacuum. Atomic rename lokal **tidak** langsung berlaku pada object storage S3. Snapshot menyalin data penuh dan mengambil tabel ke memory; hanya pantas untuk fixture/course. Produksi perlu chunked export, incremental snapshots/CDC, retention, dan commit protocol object storage.

## Hari 10: Spark

Window partitionBy(order_id) memilih latest version sebelum filter status dan groupBy(event_date,currency). Ini membutuhkan shuffle: disk partition event_date tidak menghilangkan shuffle order_id. SUM memakai Decimal, bukan float. Shuffle partitions 4, local threads 2 dan coalesce(1) sengaja untuk data kecil; bukan tuning universal.

API capstone dan DAG mem-pin snapshot_id agar Spark tidak membaca snapshot lain yang baru dipublikasikan. Output derived punya run ID sendiri; kegagalan tidak menimpa output lama. Tidak ada benchmark distributed computing atau klaim memproses 2 TB.

## Hari 11: monitoring

Sumber metrik: run/checkpoint/quality metadata, bukan isi payload pelanggan. Health mencakup regular-checkpoint freshness, latest ingestion failed, latest quality result dan task stuck >1 jam. /health sehat=200, gagal=503. /metrics memberi gauges yang di-scrape Prometheus; collection gagal=503. Alert rules tersedia, **belum ada Alertmanager/email/Slack delivery**.

Freshness mengukur waktu ingestion sukses, bukan event lateness ataupun freshness transform Spark secara independen. Daily cadence memakai threshold default 86400 detik; untuk operasional sesuaikan tolerance retry/lateness.

## Hari 12–13: delivery

Aplikasi berjalan sebagai user non-root pada container Linux AMD64 dengan Python 3.11, Java 17 dan Spark 4.0.1. Airflow mempunyai virtualenv terpisah dan mewarisi runtime aplikasi. Root Compose memisahkan ports dan volumes dari latihan awal.

CI menjalankan unit/integration, actual Spark tests, capstone, reconciled Spark-vs-warehouse, lint, compile, image build. Publish GHCR hanya manual dan menunggu reusable CI sukses. Tidak ada push repo, dispatch workflow, atau publish image yang dijalankan dalam pekerjaan ini.

Cloud architecture ada sebagai desain migrasi, bukan deployment AWS. Volume lokal tidak setara object storage/managed durability.

## Batas capstone

- Sources sintetis; histori customer/refund/products/items berasal dari seed.
- dbt rebuild table; quality gagal tidak membatalkan model yang sudah dibuat.
- Orders source current-state, bounded lookback; perubahan intermediate tidak dijamin terekam.
- Satu dbt writer/payment writer, satu broker Kafka ephemeral; bukan HA.
- PostgreSQL source/raw/warehouse masih pada instance sama.
- Tidak ada streaming event-time windows, watermark Kafka, atau CDC.
- Tidak ada soak test 24/7, beban produksi, SLA, audit compliance, ataupun security certification.
- Local demo credential, standalone Airflow admin akses localhost. Jangan dibuka ke internet.
