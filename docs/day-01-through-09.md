# Peta reference Hari 1–9

Ini peta implementasi pada copy referensi, bukan perubahan otomatis terhadap status belajar Anda. Fokusnya kode yang bisa dijalankan, dipahami, diuji, dan dibahas saat interview internship.

| Hari | Fokus | File utama | Bukti yang bisa dicoba |
|---|---|---|---|
| 1 | Kontrak dan pemisahan domain | domain/order_event.py, architecture brief, ADR-0001 | validator + 7 domain tests |
| 2 | Incremental orders, keyset, staging, raw/checkpoint atomic | ingestion/repository.py, service.py | initial load, rerun, fail sebelum finalize |
| 3 | REST payments, pagination, retry, schema validation | payment_api.py, payment_service.py, payment_repository.py | mock 429, 3 pages, duplicate/conflict tests |
| 4 | Grain, dimensions/facts, customer history | dbt/models/warehouse, day_04_warehouse.sql | as-of customer join, transaction unit price |
| 5 | Transformasi ELT terstruktur dengan dbt | dbt/models/staging dan marts | dbt build, daily finance, city/membership |
| 6 | Data quality dan integration tests | dbt/tests, schema.yml, platform.py, tests/integration | 25 data tests + quality gate |
| 7 | Orchestration Airflow | dags/nusacommerce_batch.py | 5 task DAG, retry, max_active_runs |
| 8 | Recovery, conflict, concurrency, backfill | repository.pipeline_lock/check_conflicts, service.backfill | advisory lock, hash conflict, checkpoint tidak mundur |
| 9 | Kafka pengantar, producer/consumer, replay | streaming/clickstream.py, infra/kafka | 6 event, replay idempotent, clickstream mart |

## Urutan membaca

1. README dan arsitektur reference.
2. Kontrak OrderEvent.
3. IncrementalOrderIngestion.run dan _run_window.
4. Repository: stage page, check_conflicts, finalize_run, pipeline_lock.
5. PaymentApiClient → PaymentIngestionService → PaymentRepository.
6. stg_orders → dim_customer → fct_orders → marts.
7. Test satu failure scenario sebelum membaca DAG.
8. DAG dan CLI: orchestration memanggil logic, bukan menyimpan semua logic.
9. store_event dan consume: pahami urutan DB commit lalu offset commit.

## Lima keputusan yang perlu bisa Anda jelaskan

- Mengapa staging boleh commit per page tetapi raw dan checkpoint harus atomic?
- Mengapa duplicate identik berbeda dari version conflict?
- Mengapa harga transaksi ada di fact, bukan dihitung dari current product price?
- Mengapa backfill tidak memundurkan checkpoint ingestion reguler?
- Mengapa database sink idempotent masih tidak sama dengan exactly-once lintas sistem?

## Yang sengaja belum dibuat

Spark/data lake, Kubernetes, CDC penuh, managed cloud, dashboard UI, CI/CD deployment, dan monitoring/alerting lengkap. Jangan mencantumkan komponen tersebut sebagai kemampuan implementasi project ini.

Gunakan reference untuk membandingkan hasil pekerjaan Anda. Agar portfolio benar-benar milik Anda, jelaskan keputusan, tambah satu skenario sendiri, dan rekam hasil pengujian Anda sebelum mempublikasikan.
