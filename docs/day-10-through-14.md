# Reference Hari 10–14

Ini pendamping implementasi pada copy selesai; bukan instruksi untuk melewati assessment Anda. Hari 1–9 ada di day-01-through-09.md.

## Hari 10 — Parquet, lake dan Spark

**Objectives:** bedakan disk partition dan shuffle; buat snapshot valid; dedup sebelum agregasi; pertahankan tipe uang.
**Prerequisite:** raw ingestion, SQL window, grain, retry.
**Estimasi belajar:** 3–4 jam; download/build pertama bisa lebih lama.

**Materi / WHY:** warehouse melayani tabel analitik; lake menyimpan data file untuk replay/pemrosesan lintas engine. Parquet columnar membantu pembacaan kolom dan compression. Disk partitions memangkas pembacaan berdasarkan predicate, tetapi groupBy/order_id window tetap bisa membutuhkan shuffle.

**HOW:** export REPEATABLE READ → typed Arrow → event_date partitions → checksummed manifest → publish snapshot → Spark window latest version → filter cancelled → groupBy → derived Parquet. Baca lake/snapshot.py dan lake/spark_job.py.

**WHEN / TRADEOFF:** untuk fixture ini SQL saja cukup; Spark ditambahkan agar Anda memahami batch distributed API. local[2] menjalankan dua thread pada satu mesin, bukan dua executor multi-host. Full snapshot sederhana/replayable tetapi mahal; exporter fetch-all bukan desain untuk 2 TB. coalesce(1) cocok output demo kecil, buruk untuk dataset besar.

**Contoh / mini project:** order a version1 paid lalu version2 cancelled. Hasil agregasi harus tidak memasukkan a. tests/test_spark_job.py membuktikannya.

**Latihan:** baca manifest dan temukan jumlah partitions/rows/files; bandingkan order_value Spark dengan warehouse. **Challenge:** ubah fixture menjadi dua currency dan buktikan tidak dijumlahkan bersama.

**Pembahasan:** dedup sebelum filter menghindari old paid version “hidup kembali”. Decimal menjaga presisi. Snapshot ID dipin oleh capstone/DAG.

**Common mistakes:** menganggap partition date menghapus semua shuffle; memakai float untuk money; latest pointer berubah di tengah run; banyak tiny files; mengklaim local mode sudah membuktikan cluster.
**Best practices:** tipe eksplisit, immutable raw, validate checksum, snapshot-pinned read, ukur execution plan sebelum menambah executor.

**Quiz:** Mengapa filter cancelled sebelum window salah? Mengapa current raw version bukan histori lengkap source? **Refleksi:** operasi mana yang memerlukan data bergerak antarpengolah?

Referensi: [PySpark installation/requirements](https://spark.apache.org/docs/4.0.1/api/python/getting_started/install.html). Spark 4.0.1 memerlukan Java 17 atau lebih baru; image reference menyediakan Java 17.

## Hari 11 — Monitoring dan failure signals

**Objectives:** bedakan logs/metrics/alerts; ukur health dari metadata; deteksi stale/failed quality.
**Prerequisite:** run metadata, checkpoints dan quality gate. **Estimasi:** 2–3 jam.

**Materi / WHY:** exit 0 tidak membuktikan data segar. Log menjelaskan kejadian; metric mengukur state/trend; alert memberi kondisi yang butuh tindakan.
**HOW:** monitoring.collect_health membaca checkpoint sukses, latest run, quality dan row counts. Exporter menyediakan /health dan /metrics; Prometheus scrape dan rule evaluation.
**WHEN / TRADEOFF:** gauges DB mudah dijelaskan; scraping menambah query dan hanya mengukur state yang diinstrumentasi. Tidak ada event-time lag/Spark freshness independen.

**Contoh / mini project:** quality passed=false → /health 503; rule NusaQualityFailed dapat pending lalu firing.
**Latihan:** baca metrics dan cari last_success_age_seconds. **Challenge:** simulasikan source gagal pada *_test; jangan merusak demo DB.

**Pembahasan:** marker sukses lama tetap ada setelah failure; karena itu health juga memeriksa latest run gagal. Missing success diberi sentinel -1 pada metric, bukan age nol.
**Common mistakes:** counts dianggap freshness; log payload/secret; alert tanpa runbook; menyamakan firing rule dengan notifikasi terkirim.
**Best practices:** metadata tanpa PII, threshold sesuai cadence, failure signal eksplisit dan channel notification teruji.

**Quiz:** Data lama tetapi pipeline tiap hari exit 0—apa yang belum diukur? **Refleksi:** alert mana yang dapat ditindaklanjuti?
Referensi: [Prometheus alerting rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/). Rule evaluation sendiri tidak memasang notification delivery; Alertmanager belum dikonfigurasi di reference.

## Hari 12 — Tests dan CI

**Objectives:** pisahkan unit/integration/e2e; test failures, bukan happy path saja; gate release.
**Prerequisite:** Python modules, Git dasar, database test. **Estimasi:** 2–3 jam.

**Materi / WHY:** pipeline yang menghasilkan angka salah dapat terlihat sukses. Contract tests, transaction tests dan reconciliation memeriksa risiko berbeda.
**HOW:** unittest + dedicated *_test; actual Spark cases; scripts/ci_verify.py menjalankan capstone dan membandingkan Spark daily orders dengan warehouse. CI menambah lint, compile, image build.
**WHEN / TRADEOFF:** integration lambat tetapi menguji transaksi sesungguhnya. GitHub runner berbeda dari lokal; local test bukan bukti workflow hosted sudah berjalan.

**Contoh / mini project:** CI source database terpisah dari test DB; cleanup tests tidak merusak capstone.
**Latihan:** jalankan ci_verify di container dengan kedua DB. **Challenge:** ubah agregasi menjadi filter-before-dedup dan lihat test gagal.

**Pembahasan:** separate DB adalah safety contract. Metrik test pass harus mencantumkan skips; jangan membuat fake green badge.
**Common mistakes:** tests memakai DB kerja; mocks semua layer; workflow publish tidak menunggu CI; secrets masuk artifacts.
**Best practices:** least-privilege permissions, bounded job timeout, failure cases dan evidence kecil.

**Quiz:** Mengapa unit test repository mock tidak membuktikan rollback PostgreSQL? **Refleksi:** regression mana yang paling mudah lolos?
Referensi: [GitHub PostgreSQL service containers](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers).

## Hari 13 — Deployment dan cloud mapping

**Objectives:** jalankan project konsisten; pisahkan app/Airflow dependencies; pahami yang berubah di cloud.
**Prerequisite:** Docker dasar dan CI. **Estimasi:** 2–3 jam.

**Materi / WHY:** code benar belum cukup bila runtime/dependencies/storage berbeda. Container image membungkus runtime; volume menyimpan state di luar container.
**HOW:** deploy_local → build app → source/Kafka → bootstrap/consume/capstone → monitoring; Airflow optional. App non-root; localhost bindings; app venv terpisah dari Airflow.
**WHEN / TRADEOFF:** Compose sederhana untuk portfolio, tidak setara HA/managed platform. Cloud S3/RDS memerlukan adapters, network/IAM/TLS/backup; bukan mengganti nama folder.

**Contoh / mini project:** satu perintah deployment lokal dan inspect health. **Latihan:** stop lalu start tanpa down -v; data PostgreSQL tetap ada. **Challenge:** desain rollback image tanpa mengedit applied migration.

**Pembahasan:** rollback code bukan rollback data. Atomic rename local tidak dapat dipindahkan langsung ke S3 object publish.
**Common mistakes:** volume dihapus saat cleanup; service dibuka public; admin localhost dianggap production auth; deploy cloud tanpa budget.
**Best practices:** image commit tag, secrets env, restore drill, scope deployment eksplisit.

**Quiz:** Apa yang hilang bila broker ephemeral direcreate? **Refleksi:** kapan managed service benar-benar mengurangi pekerjaan?
Referensi: [uv Docker images](https://docs.astral.sh/uv/guides/integration/docker/), [cloud mapping](deployment/cloud-design.md).

## Hari 14 — Capstone dan portfolio handoff

**Objectives:** demo end-to-end; jelaskan desain/failure modes; bedakan implementation dan claims.
**Prerequisite:** Hari 1–13. **Estimasi:** 2–3 jam.

**Materi / WHY:** reviewer internship perlu melihat project runnable, keputusan jelas, tests bermakna dan batasan jujur.
**HOW:** script deployment → CLI capstone → dbt evidence → Spark report → /health/alerts → architecture/runbook/verification.
**WHEN / TRADEOFF:** satu project saling terhubung lebih mudah dijelaskan dibanding demo library terpisah. Reference selesai bukan otomatis bukti semua kode dikuasai.

**Contoh / mini project:** rekam demo 5–7 menit memakai checklist portfolio/guide.md.
**Latihan:** tunjukkan tiga failure tests dan satu tradeoff. **Challenge:** tambahkan satu source atau satu metric dengan test sendiri.

**Pembahasan:** jawab dengan data flow, invariant dan failure point. Jangan mengklaim 2 TB, 24/7, exactly-once, atau cloud deployment tanpa bukti.
**Common mistakes:** README hanya daftar teknologi; angka impact dibuat-buat; hasil CI belum dijalankan dianggap green; raw/secret ikut Git.
**Best practices:** quickstart bersih, review limitations, reproducible evidence dan kontribusi personal.

**Quiz:** Jika diminta scale 100x, apa dua bottleneck konkret di reference? **Refleksi:** bagian mana yang bisa Anda bangun ulang tanpa melihat reference?
Referensi: [portfolio guide](portfolio/guide.md), [verification report](VERIFICATION.md), [runbook](operations/runbook.md).
