# Arsitektur

```text
Orders PostgreSQL ─┐
Payments API ──────┼─> landing ─> dbt ─> warehouse / marts
Clickstream/Kafka ─┘      └─> Parquet ─> Spark daily orders

Airflow: bootstrap -> [orders, payments] -> dbt -> quality -> lake -> Spark -> monitor
Metrics exporter -> Prometheus
```

## Ingestion

Order dibaca dengan window `start <= updated_at < cutoff` dan pagination
`(updated_at, order_id)`. Run berikutnya membaca ulang 15 menit sebelum checkpoint.
Session lock PostgreSQL membatasi satu runner per pipeline. Setiap halaman masuk
ke staging; raw data, status sukses, dan checkpoint dipublikasikan dalam satu
transaksi. Kegagalan tidak memajukan checkpoint.

Raw order memakai key `(order_id, version)`. Hash payload membedakan duplikasi
dari perubahan isi yang memakai versi sama. Backfill memakai pemeriksaan yang
sama tanpa mengubah checkpoint reguler. Source menyimpan keadaan terkini;
riwayat raw hanya memuat versi yang sempat dibaca.

Pembayaran disimpan per halaman API. Retry dimulai dari halaman pertama;
key `(payment_id, version)` dan hash payload menangani replay serta konflik.
Kafka consumer menyimpan event ke PostgreSQL sebelum commit offset. Event yang
terkirim ulang dikenali lewat `event_id` dan hash payload.

## Warehouse dan lake

Model dbt membentuk dimensi customer, product, dan date; fakta order, order item,
payment, dan refund; serta mart finance, clickstream, dan penjualan per kota.
Histori customer, product, item, dan refund berasal dari seed.

Finance menghitung pembayaran sukses dikurangi refund berdasarkan tanggal transaksi.
Spark memilih versi order terbaru sebelum mengecualikan order cancelled dan
menghitung nilai order berdasarkan tanggal dibuat. Kedua laporan memakai grain berbeda.

Export Parquet memakai transaksi `REPEATABLE READ`. Setiap snapshot memiliki manifest,
jumlah baris, dan checksum. Pointer `latest.json` diganti setelah export selesai.
Spark membaca ID snapshot yang sama dengan hasil export dan menulis hasil terpisah.

Spark berjalan sebagai `local[2]`. Export membaca tabel penuh ke memori; konfigurasi
ini ditujukan untuk dataset lokal. Kafka tidak memakai volume persisten.
