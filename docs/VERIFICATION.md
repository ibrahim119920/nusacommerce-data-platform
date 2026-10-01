# Verification report — Reference Hari 14

Tanggal: 2026-10-02 Asia/Jakarta. Copy ditingkatkan in-place dari Hari 9. Bukti tahap sebelumnya dipertahankan di verification-day09.md.

## Lingkungan

Windows PowerShell + Docker Linux AMD64. App container Python 3.11, Java 17, PySpark 4.0.1, PyArrow 18.1.0. PostgreSQL 16; dbt-core/postgres 1.9.0; Kafka 3.9.0; Prometheus 3.2.1; Airflow 3.1.0 dengan venv terpisah.

Docker Hub python/airflow masih gagal TLS pada host. Masalah build diselesaikan dengan base Python GHCR (digest dipin) dan Airflow install memakai official constraints. **Build aplikasi dan Airflow sekarang benar-benar berhasil**, bukan lagi unverified seperti report Hari 9.

## Checks yang dijalankan

| Check | Hasil nyata |
|---|---|
| Tests Linux app, RUN_SPARK_TESTS=1 | **41/41 pass, 0 skipped**, actual Spark included |
| Tests Windows tanpa Java/PySpark | 38 pass + 3 Spark skipped (41 discovered) |
| Ruff E9/F lint | Pass pada src/tests/scripts/dags |
| compileall | Pass |
| pip check native/app/Airflow | No broken requirements found |
| dbt build | **12 models + 25 data tests: PASS=37 WARN=0 ERROR=0 SKIP=0** |
| CLI capstone via Compose | Orders/payments → dbt/quality → Parquet → Spark → monitor sukses |
| CI-equivalent script | CI_VERIFY_OK; fresh separate CI/test DB; Spark/warehouse parity exact |
| Parquet snapshot | 8 orders, 6 payments, 6 clickstream dalam demo; checksums + row counts valid |
| Kafka replay pada reference existing DB | 6 produced, received 6 / inserted 0 / duplicates 6 |
| Full Airflow DAG test | **8 tasks sukses**, snapshot_id XCom, DagRun state=success |
| Airflow import errors | Tidak ada |
| Airflow standalone/UI | HTTP 200; metadata/scheduler/triggerer/dag_processor healthy |
| HTTP health positive | 200, healthy=true |
| HTTP health negative | Latest quality=false → **503**, kemudian real quality re-run → healthy=true |
| Prometheus scrape | up{job="nusacommerce"} = 1 |
| Prometheus config/rules | promtool valid; 4 alert rules |
| Prometheus rule tests | promtool test rules SUCCESS, healthy/pending-to-firing assertions |
| Compose all profiles | Valid |
| Workflow/config YAML parsing | 5 YAML files parsed |
| Local deployment wrapper | PowerShell -WithAirflow exit 0; capstone + monitoring + Airflow startup berhasil |

CI-equivalent dijalankan di app Docker image menggunakan scripts/ci_verify.py. Database utama nusacommerce_ci dan test nusacommerce_ci_test terpisah dari demo nusacommerce serta latihan asli. Pada tahap verifikasi lokal ini, original repository tidak diedit dan GitHub tidak diakses untuk mutation.

### Pengujian manual tambahan oleh pemilik project

Pada 2026-10-02, Docker/WSL sempat berhenti dan meninggalkan task Spark pada run sebelumnya sebagai `running`. Setelah layanan aktif kembali, pemilik project mengulang `airflow dags test nusacommerce_batch 2026-10-02`. Run `manual__2026-10-01T23:05:17.190463+00:00` selesai dengan `state=success` pada `2026-10-01T23:05:55.893467+00:00`; hasil ini juga dikonfirmasi melalui `airflow dags list-runs nusacommerce_batch`. Ini bukti pengujian manual, bukan scheduling otomatis atau uptime 24/7. Durasi negatif pada log berasal dari timestamp awal run yang lebih maju daripada timestamp selesai, sehingga bukan benchmark durasi aktual.

## Coverage tambahan Hari 10–14

Snapshot roundtrip, rerun immutable snapshots, partial export tidak mengganti latest pointer, checksum failure, snapshot/file path traversal. Monitoring healthy/stale/missing/failed quality/latest failed ingestion/naive time. Spark latest-cancelled semantics, Decimal money, empty input. Spark result juga direkonsiliasi terhadap warehouse (bukan hanya diuji memakai mocks).

## Expected results

### Finance (payment/refund date)

| Date | Revenue IDR | Refund IDR | Net IDR |
|---|---:|---:|---:|
| 2026-09-28 | 1.345.000 | 0 | 1.345.000 |
| 2026-09-29 | 0 | 25.000 | -25.000 |

### Spark order mart (order created date; cancelled excluded)

| Date | Order count | Order value IDR |
|---|---:|---:|
| 2026-09-27 | 3 | 464.000 |
| 2026-09-28 | 4 | 881.000 |

Clickstream 2026-10-01: page_view 3, add_to_cart 2, checkout 1. Raw versions 8; payments 6; events 6. CI fresh DB tidak menyalakan Kafka sehingga clickstream=0 di jalur CI-equivalent; deployment script menyalakan Kafka terlebih dahulu.

## Reproduce

- README quickstart / scripts/deploy_local.ps1 -WithAirflow.
- scripts/verify_reference.ps1 untuk non-Spark Windows tests.
- scripts/ci_verify.py pada Linux/Java/PySpark dengan DB utama dan *_test terpisah.
- airflow dags test nusacommerce_batch 2026-10-02 di service airflow.
- promtool test rules /etc/prometheus/alerts.test.yml di service prometheus.

Fixture cutoff harus sama/lebih baru dari regular checkpoint. Logical date pada dag test adalah tanggal demo, bukan benchmark durasi/scheduling.

## Batas verifikasi

- Hosted GitHub Actions, manual release/push GHCR, cloud/SSH deployment **belum dijalankan**.
- Tidak ada credential/resource/tagihan cloud yang dibuat.
- Notification delivery belum dipasang; alert-rule firing logic diuji dengan promtool.
- Tidak ada soak/load test, cluster multi-host, HA, CDC, atau security/compliance audit.
- Backup/restore drill belum dilakukan.
- Linux deployment bash wrapper lulus bash -n tetapi belum dieksekusi penuh; command flow ekuivalennya dan PowerShell wrapper diuji.
- NativeCodeLoader/Java incubator warnings, optional Graphviz warning, dan PySpark unittest socket ResourceWarning muncul; pengujian tetap lulus. ResourceWarning library belum diinvestigasi sebagai load/soak issue.

Folder lama reference-day09 dan project name nusacommerce_reference9 dipertahankan untuk continuity. Volumes demo dipertahankan; runtime verifikasi sementara dihapus. Layanan reference dihentikan setelah verifikasi untuk membebaskan resource.

Skill work-codex-integration digunakan; Codex CLI host masih gagal akibat optional runtime package hilang. Implementasi/verification dilakukan langsung sebagai fallback tanpa mengubah instalasi Codex.
