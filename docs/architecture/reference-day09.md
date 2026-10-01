# Arsitektur reference Hari 9

## Alur

```text
source.orders PostgreSQL ──keyset──> staging.orders ──atomic──> landing.raw_order_versions
                                        |                       + checkpoint
Payment mock REST ──retry + pages───────> landing.raw_payment_versions
Customer history/products/items/refunds fixtures ────────────> landing tables
                                                                  |
                                                         dbt staging (views)
                                                                  |
                                                         warehouse (tables)
                                                         dimensions + facts
                                                                  |
                                                            marts (tables)
                                                         finance / city-member

Clickstream fixture → Kafka topic (3 partitions) → Consumer → landing.clickstream_events
                                                  DB commit       |
                                                  THEN offset   dbt → daily_clickstream

Airflow: bootstrap → [orders, payments] → warehouse/dbt build → quality
Control: ingestion_runs, checkpoints, quality_runs
Quality: order_conflicts
```

Kafka producer/consumer demo dijalankan terpisah dari DAG batch. Daily clickstream merupakan batch aggregation atas events yang sudah dikonsumsi, bukan dashboard streaming real-time.

## Kontrak penyimpanan dan grain

| Tabel | Satu baris berarti |
|---|---|
| raw_order_versions | Satu order_id + version yang pernah diamati |
| raw_payment_versions | Satu payment_id + version |
| dim_customer | Satu customer pada satu interval histori |
| dim_product | Satu product dengan atribut saat ini |
| fct_orders | Satu order pada latest observed version |
| fct_order_items | Satu order + line_number, harga transaksi |
| fct_payments | Satu payment latest observed version |
| fct_refunds | Satu refund event |
| marts.daily_finance | Satu tanggal + currency, cash received/refunded |
| marts.orders_by_city_membership | Order date + city + membership + currency |
| landing.clickstream_events | Satu event_id yang immutable |
| marts.daily_clickstream | Satu event date + event_type |

Customer join memakai created_at order di dalam interval valid_from inklusif dan valid_to eksklusif. Histori sudah disediakan fixture; ini modeling SCD2, bukan implementasi CDC/SCD2 capture dari source hidup. City/member lama tidak berubah akibat current customer.

Finance memilih tanggal payment/refund, bukan created_at order. Revenue di sini didefinisikan sebagai payment succeeded (cash-based demo), bukan revenue recognition accounting. Refund disimpan sebagai event terpisah dengan amount positif, kemudian dikurangkan. Net negatif pada hari tanpa pembayaran bukan error.

## Failure semantics

Orders: lock session PostgreSQL mencegah dua runner menulis pipeline yang sama. Staging boleh commit per page. Final transaction mempublikasikan raw, status sukses, dan checkpoint bersama. Jika gagal, window diulang; identity unik mencegah duplicate. Same identity + different payload hash adalah conflict, dicatat dan dihentikan; bukan silently skip.

Payments: restart membaca pagination dari awal; page commit atomic, identity/version idempotent. Tidak ada durable pagination checkpoint atau incremental since token untuk payment mock.

Kafka: consumer menyimpan event di PostgreSQL lalu synchronous commit offset. Crash setelah DB commit dapat menyebabkan delivery ulang; event_id + hash menangani replay. Ini bukan atomic commit pada dua sistem dan bukan jaminan exactly-once end-to-end.

## Batasan operasional

- Source orders adalah current-state table; perubahan intermediate di antara ekstraksi bisa tidak teramati.
- Window berbasis updated_at, lookback 15 menit, safe cutoff input. Belum CDC, snapshot isolation lintas seluruh page, atau watermark yang dibuktikan dari source.
- Late data di luar lookback memerlukan backfill dengan interval benar.
- Lock orders bukan global lock untuk semua penulis warehouse/payment/stream. Jalankan satu payment writer dan satu dbt build pada satu waktu.
- dbt membangun table per model; failure test tidak membatalkan semua model yang sudah dibuat. Konsumen external perlu publication contract tambahan.
- Kafka satu broker ephemeral. Recreate broker menghapus offset/topic; DB masih menyimpan event. Demo replay fixture tetap idempotent, tetapi jangan menganggap offset koordinat tetap valid untuk stream baru setelah recreate.
- Fixture tanggal tetap; dim_date September–Oktober 2026. Perlu perluasan calendar untuk dataset baru.
- Security: localhost binding, payload sensitif tidak dilog, SQL values parameterized, secrets melalui env. Tidak ada TLS, RBAC production, secret rotation, atau PII retention enforcement.

## Tradeoff

PostgreSQL untuk source/raw/warehouse menyederhanakan setup dan transaksi tetapi tidak mensimulasikan warehouse terpisah skala besar. Rebuild dbt mudah diaudit, tetapi lebih mahal daripada incremental model. Kafka membawa cara berpikir offset/replay dengan biaya runtime tambahan; tidak diperlukan untuk ingestion orders harian. Airflow memisahkan dependency/retry dari domain logic, tetapi standalone tetap alat latihan.

Dokumen Hari 1 dan ADR-0001/0002 dipertahankan sebagai catatan tahap terdahulu. Perilaku reference terbaru dijelaskan di dokumen ini dan ADR-0003.
