# ADR-0001: Initial ingestion strategy

Status: Proposed

## Context

Berdasarkan requirements awal:
- Laporan harian divisi Finance
- Dashboard yang diperbarui setiap jam divisi Operations
- Near real-time clickstream analysis divisi Growth

Dengan sumber data utama:
- PostgreSQL OLTP
- Payment REST API
- Clickstream

## Decision

Pilihan: Incremental Batch dari PostgreSQL Read Replica

Incremental batch dilakukan dengan membaca perubahan data dari PostgreSQL read
replica. Watermark tidak hanya menggunakan `updated_at`, tetapi berupa composite
watermark `(updated_at, primary_key)`. Tuple dibandingkan secara lexicographic
dan setiap page wajib menggunakan deterministic ordering:

```sql
ORDER BY updated_at ASC, primary_key ASC
```

`primary_key` harus unik, stabil, dan non-null. Dengan aturan ini, record dengan
timestamp yang sama tetap memiliki posisi deterministik. Sebagai contoh, setelah
`(10:00, 100)` diproses, `(10:00, 101)` tetap berada setelah cursor dan tidak
terlewat. Keyset pagination menggunakan tuple `(updated_at, primary_key)` dan
tidak menggunakan `OFFSET`.

### Safe cutoff and lookback

Setiap batch menetapkan satu `safe_cutoff` yang tidak berubah selama pagination:

```text
safe_cutoff = min(
  batch_started_at_utc - safety_margin,
  replica_replay_timestamp - safety_margin
)
```

`replica_replay_timestamp` adalah timestamp transaksi terakhir yang sudah
direplay oleh PostgreSQL replica, misalnya dari
`pg_last_xact_replay_timestamp()`. `safety_margin` melindungi pipeline dari
replication lag dan clock skew yang masih berada dalam toleransi. Nilai awal yang
digunakan adalah 5 menit dan harus dikalibrasi dari metrik replication lag.
Watermark tidak boleh maju melampaui `safe_cutoff`. Jika replay timestamp tidak
tersedia, stale, atau observed lag melampaui batas operasional, batch tidak
memajukan checkpoint dan mengirim alert.

Setiap eksekusi membaca ulang interval overlap mulai dari
`checkpoint.updated_at - lookback_window` hingga `safe_cutoff`, lalu mengurutkan
record berdasarkan `(updated_at, primary_key)`. Nilai awal `lookback_window`
adalah 15 menit dan harus lebih besar daripada replication lag serta clock skew
yang ditoleransi. Dengan demikian, record dengan `updated_at=10:03` yang baru
terlihat setelah checkpoint mencapai 10:05 masih ditemukan pada pembacaan ulang.
Jika observed lag mendekati atau melampaui lookback window, publish dan kemajuan
checkpoint diblokir sampai interval aman diperluas atau replica kembali sehat.

Pembacaan overlap menggunakan semantics at-least-once. Record yang terbaca ulang
ditulis dengan idempotent upsert berdasarkan primary key dan dideduplicate
menggunakan source key, `updated_at`, serta canonical payload hash. Record identik
tidak membuat duplikasi; perubahan yang valid memperbarui state sesuai aturan
version handling pada architecture brief.

### Checkpoint advancement

Checkpoint composite hanya diperbarui ke tuple maksimum yang tidak melebihi
`safe_cutoff` setelah seluruh target write, deduplication, dan quality check untuk
batch berhasil melakukan durable commit. Apabila target commit berhasil tetapi
penyimpanan checkpoint gagal, batch berikutnya membaca ulang overlap dan
idempotent upsert mencegah duplikasi. Checkpoint tidak pernah dimajukan terlebih
dahulu dan tidak dimajukan untuk batch yang gagal atau publish yang diblokir.

Kontrak sumber mewajibkan `updated_at` diisi saat perubahan di-commit dan tidak
boleh dimundurkan secara arbitrer. Pelanggaran yang menghasilkan timestamp lebih
lama daripada lookback window adalah blocking data-quality failure dan menjadi
revisit trigger untuk memperbesar window atau beralih ke CDC.

Operasi delete ditangkap menggunakan mekanisme soft delete
(kolom `deleted_at` atau `is_deleted`). Apabila di masa depan
dibutuhkan hard delete, mekanisme tersebut akan dipertimbangkan
kembali, misalnya melalui CDC atau tabel audit.

Dashboard dan proses ETL juga mempertimbangkan kemungkinan
replication lag pada read replica. Oleh karena itu, data yang
ditampilkan memiliki toleransi keterlambatan sesuai SLO yang
ditetapkan.

## Alternatives considered

Alternatif: Change Data Capture (CDC)

CDC mampu menangkap perubahan data secara lebih cepat, termasuk
insert, update, dan delete, dengan beban query yang lebih rendah
dibandingkan incremental batch. Namun, implementasinya memerlukan
infrastruktur, monitoring, dan kompleksitas operasional yang lebih
tinggi sehingga belum dipilih pada tahap awal.

Alternatif: Direct OLTP Query

Direct query ke database OLTP memberikan akses ke data terbaru
tanpa jeda replikasi. Namun, pendekatan ini berpotensi
meningkatkan beban query pada sistem transaksi sehingga dapat
memengaruhi performa aplikasi apabila tidak dikendalikan dengan
baik.

## Positive consequences

Konsekuensi positif dari Incremental Batch menggunakan read replica
adalah implementasinya relatif cepat, sederhana, dan mengurangi
beban query pada database OLTP primary karena proses analitik tidak
langsung mengakses database transaksi.

Pendekatan ini juga cukup untuk memenuhi kebutuhan laporan harian
Finance dan dashboard per jam Operations tanpa memerlukan infrastruktur
streaming yang lebih kompleks.

## Negative consequences

Composite watermark dan lookback window mengurangi risiko record terlewat akibat
timestamp yang sama dan replication lag. Risiko residual tetap ada jika source
memundurkan `updated_at` melampaui lookback window atau lag melebihi batas tanpa
terdeteksi. Karena itu, metrik lag, safe cutoff, ukuran overlap, dan jumlah record
hasil replay harus dimonitor.

Konsekuensi lainnya adalah kebutuhan komputasi yang relatif tinggi
dibandingkan opsi Direct OLTP Query, terdapat operasi tambahan yang berasal
dari instance replica, replication/WAL, storage, query, dan pipeline compute,
sehingga komputasi dan I/O dapat meningkat seiring bertambahnya volume perubahan
data.

## Failure modes

Opsi ini akan mengalami failure ketika:
- Perubahan skema mendadak: kolom di tabel sumber dihapus, berganti
  nama, atau tipe datanya berubah sebelum skrip batch diperbarui.
- Nilai Null pada Kolom Kunci: Kolom penanda waktu (updated_at) atau
  ID incremental secara tidak sengaja berisi nilai NULL.
- Data corrupt: Format data baru yang masuk tidak sesuai dengan
  validasi skrip penerima (misal: format tanggal berubah).
- Kegagalan di antara durable commit dan penyimpanan checkpoint menyebabkan
  interval dibaca ulang. Idempotent upsert wajib mencegah duplicate.
- Replication lag yang tinggi menyebabkan read replica tertinggal
  cukup jauh dari primary sehingga dashboard tidak memenuhi target
  freshness data.
- `updated_at` dimundurkan melampaui lookback window atau tidak mencerminkan waktu
  perubahan sehingga record berada di luar interval overlap.

## Security implications

- Akses script ke dalam database sekaligus memberi akses ke dalam
  data-data privat pengguna
- Akses script memerlukan token akses yang perlu disimpan dengan
  aman
- Keamanan metode pengiriman data hasil query ke Data Platform.

## Cost and operational impact

Pendekatan ini menambah biaya operasional berupa penyediaan read
replica, penyimpanan WAL untuk proses replikasi, serta sumber daya
komputasi yang digunakan proses batch.

Penggunaan read replica mengurangi beban query analitik pada
database OLTP primary, tetapi tetap menambah overhead replikasi dan
pemrosesan WAL sehingga bukan berarti tanpa dampak terhadap sistem
transaksi.

## Revisit triggers

Pendekatan ini perlu dievaluasi kembali apabila salah satu kondisi
berikut terjadi:

- SLO freshness data tidak tercapai secara konsisten (misalnya
  dashboard terlambat lebih dari 15 menit dari target).
- Replication lag read replica secara konsisten melebihi batas yang
  disepakati (misalnya lebih dari 5 menit) (initial/provisional
  thresholds)
- Volume perubahan data meningkat sehingga incremental batch harus
  melakukan scan lebih dari 20% tabel pada setiap eksekusi (initial/
  provisional thresholds)
- Kebutuhan bisnis berubah menjadi near real-time untuk sebagian
  besar pipeline sehingga latency incremental batch tidak lagi
  memenuhi kebutuhan.
- Frekuensi update pada baris yang sama meningkat sehingga biaya
  pemrosesan incremental batch menjadi tidak efisien dibandingkan
  pendekatan CDC.
