# ADR-0003: Copy reference Hari 9

Status: accepted untuk demo pembelajaran lokal.
Tanggal: 2026-10-02.

## Konteks

User meminta copy yang sudah diselesaikan hingga Hari 9 tanpa mengubah repository latihan. Sasaran: portfolio internship yang runnable dengan ruang lingkup terbatas, bukan platform perusahaan ber-HA.

## Keputusan

- Copy sibling terpisah, tanpa .git, .env asli, atau virtualenv asli.
- Root compose memakai project name dan port terpisah: PostgreSQL 55439, mock payments 8009, Kafka 19099, Airflow 8089.
- Orders dan payments mengarsipkan version yang diamati; version immutable diverifikasi dengan hash.
- SQL/dbt membentuk warehouse dari latest observed records dan fixture histori.
- Quality tests menjadi gate orchestration; failure tercatat, tidak diperlakukan sebagai sukses.
- Backfill memakai lock dan tidak mengubah checkpoint reguler.
- Kafka consumer at-least-once dengan sink PostgreSQL idempotent.
- App dependencies dipisahkan dari Airflow melalui virtualenv.
- Artifacts lama dipertahankan sebagai histori; README root menjadi entry point reference.

## Konsekuensi

Mudah direproduksi dan dijelaskan dalam interview, tetapi source sintetis, volume kecil, dan beberapa tabel berasal dari seed. Full Docker app/Airflow build belum terverifikasi pada host ini karena registry download gagal. Actual DAG tasks diuji di runtime Linux alternatif, bukan dianggap bukti deployment UI.

## Alternatif

Semua logic di DAG: lebih cepat ditulis tetapi lebih sulit unit test/reuse.
Warehouse cloud: lebih realistis operasional tetapi menambah biaya dan credential.
Kafka untuk semua ingestion: memperluas kompleksitas tanpa kebutuhan demo batch.
Exactly-once distributed transaction: tidak diterapkan; replay + identity/hashing cukup untuk tujuan latihan ini.
