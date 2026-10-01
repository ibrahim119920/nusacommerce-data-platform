# Portfolio handoff

## Demo 5–7 menit

1. Tunjukkan architecture dan satu DAG; jelaskan pemisahan logic dari orchestration.
2. Jalankan deployment lokal atau tampilkan report terverifikasi.
3. Tunjukkan rerun/replay tidak menambah raw duplicates.
4. Jelaskan grain fact, harga transaksi dan customer as-of join.
5. Tunjukkan Parquet manifest + output Spark, dan parity dengan warehouse.
6. Tunjukkan health/Prometheus alert rules serta satu failure test.
7. Tutup dengan limitation dan prioritas perbaikan, bukan klaim production-ready.

## Checklist sebelum GitHub

- Jangan commit .env, .venv, artifacts raw, dbt target/logs, volume dump atau token.
- README runnable, architecture, ADR, tests dan verification report ada.
- Upload hanya setelah Anda membaca serta dapat menjelaskan implementation.
- Ambil screenshot DAG sendiri ketika UI berjalan; tidak memakai badge CI green sebelum workflow sungguh lulus.
- Repository portfolio: [nusacommerce-data-platform](https://github.com/ibrahim119920/nusacommerce-data-platform). Working copy reference tetap terpisah dari folder latihan asli.
- Lisensi jangan dipilih atas nama pemilik tanpa keputusan eksplisit.
- Jelaskan bantuan mentor/AI secara jujur jika ditanya.

## Contoh bullet CV, setelah Anda memahami implementasinya

“Built a reproducible e-commerce data pipeline using Python, PostgreSQL, dbt, Airflow and Kafka, with Parquet snapshots, Spark batch transformations, data-quality checks and local Docker deployment.”

Jangan menambahkan throughput, uptime, users, revenue impact, cloud deployment, atau exactly-once yang belum dibuktikan. Masukkan angka test terbaru hanya dari verification report nyata.

## Interview practice

- Raw checkpoint dan sink atomic: failure mana yang menyebabkan replay?
- Mengapa order latest cancelled harus dibuang setelah dedup, bukan sebelum?
- Bagaimana customer history bisa membuat historical report berubah jika join salah?
- Bagaimana database commit-before-offset mencegah data loss tetapi tetap memberi duplicates?
- Apa yang berbeda antara event-date partition dan Spark shuffle partition?
- Apa yang belum selesai bila CI lulus tetapi restore belum pernah diuji?
- Jika volume menjadi 2 TB, mana bottleneck pertama exporter ini?
- Apa yang harus berubah sebelum local filesystem publisher dipindahkan ke S3?

Pembahasan ringkas: cari jawaban pada ADR, architecture dan tests, lalu tunjukkan baris implementasi terkait. Untuk interview, jawab alasan dan failure mode, bukan hanya menyebut library.

## Pengembangan berikutnya (optional)

Satu improvement cukup: source baru, incremental dbt, streaming lag metrics, durable Kafka logs, atau S3 adapter yang diuji. Tambahkan measurable acceptance criteria dan test; tidak perlu menambah lima teknologi sekaligus.
