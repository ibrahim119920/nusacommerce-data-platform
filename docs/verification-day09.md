# Verification report — 2026-10-02 (Asia/Jakarta)

## Lingkungan

Windows PowerShell; Python 3.11.9 lokal; Docker Linux containers; PostgreSQL 16; dbt-core/dbt-postgres 1.9.0; Kafka 3.9.0 via Strimzi image 0.45.0. Airflow 3.1.0 diuji di container Linux sementara dengan Python 3.10 dan virtualenv aplikasi terpisah. Semua database/container memiliki nama reference, terpisah dari project asli.

## Hasil terverifikasi

| Check | Hasil |
|---|---|
| Python unittest | **24/24 pass**, 0 skip, termasuk integration ke nusacommerce_test |
| pip check aplikasi | No broken requirements found |
| compileall src/scripts/dags | Exit 0 |
| dbt build | **12 models + 25 data tests; PASS=37 WARN=0 ERROR=0 SKIP=0** |
| Python quality checks | 5 checks bernilai 0 (tidak ada violation) |
| Negative quality scenario | Net finance ditambah 1 sementara → exit 1, gagal tercatat; nilai dikembalikan → pass |
| Kafka producer | 6 delivered |
| Kafka consumer awal | received 6, inserted 6, duplicates 0 |
| Kafka replay | received 6, inserted 0, duplicates 6 |
| Airflow DAG test | bootstrap, orders, payments, warehouse, quality sukses; DagRun success |
| Backfill | 7 extracted, 0 inserted, 7 duplicates; checkpoint_advanced=false |
| Docker Compose config | Valid untuk tools/streaming/orchestration profiles |

Unit/integration mencakup timeout retry, HTTP429 retry cursor yang sama, retry503 terbatas, 401 tanpa retry, invalid shape, pagination loop, persistence failure, page rollback, replay, same-version conflict, lock runner kedua, empty window, rollback raw/checkpoint, dan backfill.

## Output dataset

Finance:

| Date | Revenue IDR | Refund IDR | Net IDR |
|---|---:|---:|---:|
| 2026-09-28 | 1.345.000 | 0 | 1.345.000 |
| 2026-09-29 | 0 | 25.000 | -25.000 |

Clickstream pada 2026-10-01: page_view 3, add_to_cart 2, checkout 1. Customer history 6 rows (5 customer dengan 1 perubahan), products 3, latest orders 8, order items 8, payments 6, refunds 1.

## Cara mengulang

Ikuti README quickstart; jalankan scripts/verify_reference.ps1 untuk Python tests. Jalankan cli dbt, quality, summary untuk warehouse. Producer/consumer dua kali membuktikan replay. Untuk Airflow di lingkungan dengan image tersedia: airflow dags test nusacommerce_batch 2026-10-02 di service Airflow.

Test database sengaja terpisah karena integration tests menghapus fixture antara skenario. Jangan mengarahkan TEST_POSTGRES_URL ke demo atau database kerja.

## Belum diverifikasi / batas bukti

Unduhan python:3.11-slim dan apache/airflow:3.1.0-python3.11 mengalami TLS/EOF dari registry/CDN pada host ini. Karena itu **build Dockerfile app/Airflow, startup UI standalone, dan scheduled run dari scheduler belum terverifikasi**. DAG dieksekusi nyata dengan Airflow 3.1.0 pada runtime Linux alternatif; ini bukan bukti deployment penuh.

Tidak ada load/soak test 24/7, uji cluster multi-broker, cloud deployment, atau SLA production. Hasil yang lulus berlaku untuk fixture kecil, bukan klaim performa skala industri.

Runtime/container sementara untuk verifikasi dihentikan/dihapus setelah selesai. Volume PostgreSQL reference dipertahankan agar hasil demo dapat dilihat setelah docker compose up -d postgres. Dependency .venv lokal disediakan tetapi dapat dibangun ulang dari requirements-reference.txt. Tidak ada credential .env milik repository asli yang disalin.

Skill work-codex-integration mengarahkan workflow ke Codex CLI. CLI host tidak dapat dijalankan akibat package runtime hilang; implementasi dan verifikasi dilakukan langsung sebagai fallback, tanpa memasang/mengubah Codex.
