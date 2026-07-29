# NusaCommerce Architecture Brief v0.1

## 1. Business goal

Menyediakan dataset, laporan, dan sistem analisis transaksi realtime yang dapat
digunakan sebagai pertimbangan pengambilan keputusan yang reliabel.

## 2. Consumers and decisions

Pengguna data adalah tim analisis dari berbagai bidang: finansial, operasional,
teknologi, dll. Keputusan bisnis dapat berupa kebijakan tarif aplikasi dan
refund, layouting web/aplikasi dan recommendation oleh tim IT, pembangunan
infrastruktur berdasarkan titik kepadatan customer, dan sebagainya.

Dari informasi yang sudah diberikan, Finance membutuhkan laporan harian,
Operations membutuhkan dashboard per jam, dan Growth membutuhkan data clickstream
mendekati real-time.

## 3. Data products

Data Product: hourly_sales_operations
  Owner: Divisi Operational (didukung Data Engineering untuk pengelolaan pipeline
         data).
  Konsumen:
    Divisi Operational
    Divisi Marketing
    Manajemen
  Keputusan yang didukung:
    Memantau performa operasional setiap jam.
    Menganalisis sebaran lokasi customer dan delivery area.
    Mengoptimalkan alokasi kurir dan kapasitas operasional.
    Mengidentifikasi jam-jam sibuk untuk perencanaan operasional.
  Grain:
    Satu baris data untuk setiap kombinasi jam × area pengiriman (delivery area).
    Kolom/Metric utama:
    transaction_hour
    delivery_area
    customer_city
    total_orders
    total_items
    total_transaction_value
    average_order_value
  Freshness:
    Data diperbarui setiap 1 jam.
    Maksimum keterlambatan data 1 jam.
  Quality Contract Mart:
    Tidak boleh terdapat lebih dari satu baris untuk kombinasi transaction_hour
    dan delivery_area.
    transaction_hour dan delivery_area wajib terisi.
    total_orders, total_items, dan total_transaction_value tidak boleh bernilai
    negatif.
    average_order_value harus konsisten dengan hasil perhitungan agregasi.
    Tidak ada duplikasi transaction_id sebelum data diagregasi.
    Kelengkapan data minimal 99%.
  Quality Contract (fact atomik, sebelum agregasi)
    transaction_id unik (atau order_item_id unik jika grain fact adalah item).
    Nilai transaksi tidak negatif.
    Timestamp transaksi wajib terisi.
    Tidak ada record korup atau gagal diparse.

Data Product: daily_finance_reconciliation
  Owner: Divisi Finance (didukung Data Engineering untuk pengelolaan pipeline data).
  Konsumen:
    Divisi Finance
    Accounting
    Manajemen
  Keputusan yang didukung:
    Melakukan rekonsiliasi transaksi harian.
    Memantau kontribusi setiap metode pembayaran.
    Menghitung dan mengevaluasi refund rate.
    Memantau penjualan bersih (net sales) harian.
  Grain:
    Satu baris data untuk setiap kombinasi tanggal × metode pembayaran.
    Kolom/Metric utama:
    transaction_date
    payment_method
    total_sales
    total_refund
    refund_rate
    number_of_transactions
    net_sales
  Freshness:
    Data diperbarui setiap hari setelah proses penutupan transaksi (end of day).
  Quality Contract (mart)
    Kombinasi (transaction_date, payment_method) harus unik.
    payment_method harus berasal dari daftar yang valid.
    refund_rate harus konsisten dengan rumus yang disepakati.
    Kelengkapan data minimal 99%.
  Quality Contract (fact atomik)
    transaction_id unik.
    Nilai refund total tiap transaksi tidak boleh melebihi nilai order total.
    Setiap transaksi memiliki metode pembayaran yang valid.

## 4. Source inventory

Terdapat tiga (3) sistem sumber data:

PostgreSQL OLTP, menjadi sumber utama data perusahaan: data customer, product,
seller,
order, dan sebagainya.
- Data dimiliki oleh Database Administrator
- Data orders adalah satu-satunya data dengan perubahan/pertumbuhan cepat
- Metode yang digunakan adalah incremental batch

Payment REST API adalah sumber data untuk payments, refunds, dan status transaksi.
- Dimiliki oleh payment team
- Operational API perusahaan untuk me-manage customer payment.
- Memiliki rate limit, sehingga memerlukan penjadwalan ketat agar tidak melebihi
  limit.

Clickstream
- Frontend-owned
- Tersedia data baru secara real-time

## 5. Functional requirements

Sistem yang dibangun harus memenuhi kebutuhan bisnis berikut:

- Pengguna dapat melihat dashboard operasional yang diperbarui setiap jam.
- Pengguna dapat mengakses laporan finansial harian yang menampilkan kondisi bisnis
  terkini.
- Pengguna dapat melihat metrik bisnis, meliputi:
  - GMV (Gross Merchandise Value) per jam.
  - Revenue bersih setelah memperhitungkan refund.
  - Refund rate berdasarkan metode pembayaran.
  - Revenue berdasarkan kota transaksi.
- Pengguna dapat melakukan drill-down dari ringkasan dashboard hingga detail order
  dan order item.
- Pengguna dapat mengakses data transaksi, pembayaran, refund, pelanggan, penjual,
  produk, dan aktivitas pengguna dalam satu dataset analitik yang terintegrasi.
- Pengguna memperoleh data analitik yang telah melalui proses validasi sehingga
  konsisten dan dapat digunakan sebagai dasar pengambilan keputusan.
- Setiap divisi (Finance, Operations, IT, dan Marketing) dapat mengakses dataset yang
  sesuai dengan kebutuhan analisis dan pelaporan masing-masing.
- Pengguna internal dapat mengakses dataset analitik sesuai hak akses yang diberikan.
- Pengguna selalu memperoleh hasil analisis yang mencerminkan pembaruan data terbaru,
  termasuk apabila terdapat perubahan data setelah proses sebelumnya.

## 6. Non-functional requirements

Performance
-  Pipeline mampu memproses minimal 5 juta perubahan data PostgreSQL OLTP per
   hari.
-  Dashboard operasional tersedia maksimal 1 jam setelah perubahan transaksi
   terjadi.
-  Laporan finansial harian tersedia sebelum pukul 00.30 hari berikutnya.

Availability & Reliability
-  Tingkat keberhasilan pipeline minimal 99,9% dari seluruh jadwal eksekusi.
-  Recovery dari kegagalan pipeline dilakukan secara otomatis menggunakan
   checkpoint dan mekanisme rerun.
-  Recovery Time Objective (RTO) maksimum satu jam untuk seluruh platform.

Scalability
-  Sistem mampu menangani peningkatan volume transaksi tanpa perubahan arsitektur
   utama.
-  Pipeline dapat diskalakan secara horizontal untuk menangani pertumbuhan data
   transaksi maupun clickstream.

Data Quality
-  Data completeness minimal 99,9% pada seluruh kolom kritikal.
-  Seluruh data duplikat harus dihilangkan sebelum memasuki warehouse.
-  Seluruh transformasi harus bersifat deterministic sehingga menghasilkan output
   yang konsisten ketika dilakukan reprocessing.

Security
-  Data Platform hanya memiliki akses read-only terhadap PostgreSQL OLTP.
-  Data PII hanya dapat diakses oleh pengguna yang memiliki otorisasi sesuai role
   (Role-Based Access Control).
-  Seluruh komunikasi antar komponen menggunakan koneksi terenkripsi (HTTPS/TLS).

Maintainability
-  Seluruh pipeline memiliki logging, monitoring, alerting, dan audit trail.
-  Pipeline mendukung rerun berdasarkan checkpoint tanpa harus memproses ulang
   seluruh data.

Compatibility
-  Sistem harus tetap menjaga performa PostgreSQL OLTP dan tidak mengganggu beban
   transaksi operasional.
-  Pengambilan data dari Payment REST API harus mematuhi rate limit yang diberikan

## 7. SLI and SLO

Service Level Indicator
- data_freshness = current_time - max(source_timestamp)
  Data freshness adalah selisih antara waktu pemeriksaan dan timestamp sumber
  terbaru yang berhasil dipublikasikan ke Gold Layer.
- critical_field_completeness = non_null_values / expected_values
  Persentase nilai pada kolom-kolom kritis yang terisi (non-null) terhadap
  jumlah nilai yang seharusnya tersedia.
- availability = up_time / (down_time + up_time)
  Availability adalah persentase waktu layanan pipeline tersedia untuk
  menjalankan workload sesuai fungsinya.
- run_completion = run_completed / (run_scheduled)
  run completion adalah persentase run yang berhasil terselesaikan hingga
  tahap terakhir (dashboard update) tanpa error.
- lateness_lag = processed_timestamp - event_timestamp
  Lateness lag adalah selisih antara waktu event terjadi di sumber dan waktu
  event tersebut selesai diproses oleh pipeline.

Service Level Objective
- 97,5% hasil pemeriksaan selama periode 30 hari pada Gold Layer menunjukkan
  nilai data_freshness tidak melebihi 60 menit.
- 99.9% nilai pada kolom krusial Silver dan Gold Layer harus terisi (non-null)
  selama rolling 30 hari.
- Availability minimal 99% selama rolling 30 hari.
- 99.9% run yang dijadwalkan harus selesai sukses selama rolling 30 hari.
- 95% perubahan pada Silver Layer diproses maksimal 1 jam sejak event terjadi
  selama rolling 30 hari.

## 8. Current and future architecture

Current architecture

  Arsitektur saat ini menggunakan incremental batch untuk PostgreSQL read replica
  dan Payment REST API. Clickstream dan Kafka belum menjadi bagian dari current
  flow.

  PostgreSQL read replica ──┐
                            ├── incremental batch ──► Raw Data Lake (Bronze)
  Payment REST API ─────────┘                         MinIO/S3
                                                          │
                                                Python / Spark / dbt
                                                          │
                                                          ▼
                                                PostgreSQL Warehouse (Silver)
                                                          │
                                                Facts + Dimensions (Gold) → Marts
                                                          │
                                                          ▼
                                                    Dashboard/Reports

  Airflow mengatur dependency dan scheduling. Tests, data quality, logs, metrics,
dan alerts melindungi semua tahap.

Future architecture

  Clickstream ────────► Kafka ───────────────► Raw Data Lake (Bronze)
  PostgreSQL OLTP ────► CDC (conditional) ───► Raw Data Lake (Bronze)

  Alur Clickstream melalui Kafka merupakan target pengembangan future. PostgreSQL
  beralih dari incremental batch ke CDC hanya jika satu atau lebih revisit trigger
  pada ADR-0001 terpenuhi dan perubahan tersebut disetujui melalui ADR baru.

## 9. Source of truth per layer

Terdapat lima layer data, yang menjadi SoT untuk:
- REST API/OLTP
  Source of truth untuk operasional bisnis
- Raw/Bronze - data mentah yang diambil dari PostgreSQL OLTP dan Payment
  Source of truth untuk ingestion system truth
- Staging/Silver - data hasil cleaning dan deduplication
  Not a source of truth
- Warehouse/Gold - data hasil transformasi untuk memperoleh insight
  Source of truth untuk analytical model truth
- Mart - hasil analisis berupa kontrak data untuk use case tertentu
  Source of truth untuk kontrak konsumsi
- Dashboard - data yang ditampilkan kepada pengguna
  Not a source of truth

## 10. Failure and recovery

Failure and recovery berikut mencakup proses dalam current architecture.

Raw Data Lake
  API rate limit (429)              read retry-after kemudian re-run;
                                    exponential backoff; send alert.
  API internal server error (500)   retry dengan exponential backoff;
                                    incremental fetch.
  Write failure                     check saved checkpoint/checksum,
                                    rerun dengan append, page identifier,
                                    idempotent insert, dan
                                    checkpoint setelah durable commit

Data ETL/ELT
  Invalid data                      apply the data-quality failure policy below
  Transformation failure            rerun from checkpoint dengan
                                    MERGE/UPSERT

Load to Warehouse
  Write failure                     check saved checkpoint/checksum,
                                    rerun dengan MERGE/UPSERT

Gold Layer Construction
  Fact/Dim table build failure      re-run dari data staging/silver
  Data marts build failure          re-run dari Fact/Dim table

Late-arriving Data Processing
  Version handling                  apply the version-handling policy below

### Data-quality failure policy

#### Non-blocking failures

Pipeline boleh melanjutkan pemrosesan record yang valid apabila error terisolasi
pada record tertentu dan jumlahnya masih berada di bawah threshold. Contohnya:

- field wajib hilang atau memiliki tipe/format yang salah;
- `event_type`, currency, timezone, atau version tidak memenuhi kontrak;
- amount tidak dapat diparse sebagai `Decimal`; atau
- referensi dimensi belum tersedia dan record aman ditunda sebagai late-arriving
  data.

Record tersebut ditulis ke quarantine dengan reason code, nama field yang gagal,
source, waktu ingestion, contract version, lokasi raw record, dan replay status.
Nilai payload dan PII tidak ditulis ke log. Record valid dalam batch yang sama
tetap dapat diproses.

#### Blocking failures

Publish partition atau batch ke Gold Layer dan data mart harus diblokir apabila:

- jumlah invalid record melewati threshold;
- terjadi schema drift struktural, seperti kolom kritis hilang atau berubah tipe
  pada sebagian besar batch;
- primary key tidak dapat digunakan untuk deduplication atau idempotent merge;
- uniqueness, reconciliation finansial, atau quality contract kritis pada hasil
  agregasi gagal;
- output tidak lengkap akibat kegagalan transformasi atau write; atau
- ditemukan event dengan key dan version yang sama tetapi payload berbeda.

Data yang terakhir berhasil dipublikasikan tetap tersedia. Batch yang gagal tidak
boleh menggantikan snapshot atau partition terakhir yang valid.

#### Invalid-record threshold

Threshold awal per source partition atau satu scheduled batch adalah maksimum
`0,5%` dan maksimum `100` invalid record. Kedua syarat harus terpenuhi agar
kegagalan tetap non-blocking. Jika salah satu batas terlampaui, publish diblokir.
Satu kegagalan quality contract kritis tetap blocking tanpa memperhatikan rasio.
Threshold ini bersifat initial/provisional dan harus dievaluasi setelah tersedia
30 hari metrik produksi.

#### Alert ownership

- Non-blocking failure mengirim warning ke channel operasional Data Engineering
  dan masuk ke ringkasan kualitas data untuk data product owner.
- Blocking failure melakukan paging ke Data Engineering on-call dan mengirim alert
  ke data product owner terkait: Operations untuk `hourly_sales_operations` dan
  Finance untuk `daily_finance_reconciliation`.
- Dugaan paparan PII atau pelanggaran akses juga diteruskan ke Security on-call.

#### Repair and replay

Data diperbaiki pada source atau melalui correction rule yang telah direview.
Record hasil perbaikan kemudian direplay dari quarantine menggunakan source key
dan `event_id` yang sama. Replay menjalankan kembali parsing, contract validation,
deduplication, serta seluruh quality check. Penulisan ke Silver dan Gold dilakukan
dengan idempotent `MERGE`/`UPSERT`; checkpoint baru disimpan hanya setelah durable
commit. Partition yang sebelumnya diblokir dipublikasikan secara atomik setelah
semua blocking check lulus. Setiap replay menyimpan audit link ke record quarantine
asal, alasan perbaikan, pelaksana, dan waktu replay.

### Version-handling policy

Perbandingan version dilakukan untuk entity key yang sama dengan canonical payload
hash untuk mendeteksi duplicate dan conflict:

- version lebih tinggi adalah kandidat update. Record harus melewati contract dan
  data-quality validation sebelum menggantikan state sebelumnya;
- version lebih rendah diabaikan secara idempotent sebagai stale event;
- version dan payload hash yang identik diabaikan secara idempotent sebagai exact
  duplicate; dan
- version sama tetapi payload hash berbeda adalah conflict. Record baru tidak
  boleh menimpa state yang sudah ada, dimasukkan ke quarantine, memblokir publish
  partition terkait, serta harus diinvestigasi oleh Data Engineering on-call dan
  data product owner.

Stale event dan exact duplicate dicatat sebagai metric teragregasi, bukan sebagai
payload di log dan bukan sebagai quarantine record.

## 11. Security and PII

Authentication
- IAM
- Role Based Access Control

Authorization
- Finance hanya dapat melihat revenue.
- Marketing tidak dapat melihat payment detail.
- IT tidak dapat melihat PII.

Encryption
- TLS saat data transit
- AES-256 saat data disimpan
- Sensitive Data

Masking
- email
- nomor telepon

Audit
- Seluruh akses data dicatat.

## 12. Assumptions

- PostgreSQL OLTP tersedia selama 24 jam. Apabila dalam masa maintenance,
  seluruh sistem kecuali dashboard akan idle (atau maintenance)
- Seluruh primary key unik
- Seluruh timestamp disamakan dalam UTC

## 13. Out of scope

Komponen sistem data yang tidak dikerjakan dalam scope Data Platform
- Operational PostgreSQL OLTP. Database sepenuhnya dikelola oleh Database
  Administrator. Data Platform hanya memiliki akses read database.
- Payment REST API. Data Platform hanya memiliki akses untuk mengambil
  data melalui API dengan batasan yang telah ditetapkan.
- Dashboard maintenanche. Data Platform hanya berkewajiban menyediakan
  supply data untuk dashboard.

## 14. Open questions

- Bagaimana tingkat urgensi near real-time clickstream?
- Sebagai pengembangan lebih lanjut, adakah output lain yang diharapkan
  dari Data Platform yang sedang dibangun?
