# Rangkuman Implementasi Hari 2

Tanggal: 1 Oktober 2026

## Tujuan

Membangun pipeline latihan yang mengambil orders dari PostgreSQL, memprosesnya
per page, menyimpan snapshot ke raw storage, dan aman dijalankan ulang dengan
asumsi satu runner serta payload yang immutable pada setiap `(order_id, version)`.

## Pekerjaan yang dilakukan

| File | Implementasi |
|---|---|
| `src/nusacommerce/ingestion/models.py` | `ExtractionWindow` immutable, validasi timezone dan urutan batas waktu |
| `src/nusacommerce/ingestion/repository.py` | Class repository dengan engine yang diberikan dari entry point; SQL untuk checkpoint, run, pagination, staging, finalisasi, dan status gagal |
| `src/nusacommerce/ingestion/service.py` | Koordinasi window tetap, lookback 15 menit, loop pagination, finalisasi, dan ringkasan counts |
| `scripts/run_incremental_orders.py` | CLI dengan `--safe-cutoff`, `--page-size`, serta `POSTGRES_URL` |
| `tests/integration/test_incremental_ingestion.py` | Tiga integration tests PostgreSQL: initial load, rerun, rollback dan recovery |
| `tests/integration/__init__.py` | Memasukkan integration tests ke unittest discovery |
| `pyproject.toml` | Dependency SQLAlchemy, pandas, dan psycopg binary |
| `infra/docker/docker-compose.yaml` | Konfigurasi credential melalui environment variable |
| `.env.example` | Contoh konfigurasi lokal tanpa credential nyata |
| `docs/adr/0002-processing-semantics.md` | Keputusan transaction, checkpoint, retry, dan batas latihan |
| `README.md` | Setup database, migration, seed, command pipeline, dan integration tests |

Kode hashing yang sudah ada tetap digunakan. Struktur migration dan data seed
yang telah dibuat sebelumnya tetap menjadi dasar pipeline. Komentar seed tentang
konflik diperbarui agar sesuai dengan cakupan latihan sederhana ini.

## Alur pipeline

1. Baca checkpoint terakhir. Jika belum ada, mulai dari 2026-01-01 UTC.
2. Jika sudah ada checkpoint, mulai dari checkpoint dikurangi 15 menit.
3. Tetapkan window `[start, safe_cutoff)` sekali untuk seluruh run.
4. Buat run ID baru dan status `running`.
5. Baca setiap page dengan urutan `(updated_at, order_id)` dan simpan ke staging.
6. Dalam satu transaction, masukkan raw versions, perbarui checkpoint, dan tandai
   run sebagai `succeeded`.
7. Jika gagal sebelum commit, finalisasi rollback. Catat status `failed` dalam
   transaction terpisah; staging tetap tersedia untuk diagnosis.
8. Retry memakai run ID baru dan membaca ulang window dari checkpoint terakhir.

Raw storage memiliki primary key `(order_id, version)`. `ON CONFLICT DO NOTHING`
mencegah key versi yang sudah ada dimasukkan lagi. Count `duplicates` mengukur key
yang sudah tersimpan; pada tahap ini hash belum dibandingkan untuk klasifikasi konflik.

## Hasil pengujian

Pengujian dijalankan pada PostgreSQL 16 di container sementara bernama
`nusacommerce-day2-test`, menggunakan database `nusacommerce_test`. Database demo
utama tidak dipakai atau dikosongkan untuk pengujian.

| Skenario | Hasil terverifikasi |
|---|---|
| Initial load, page size 2 | 8 extracted, 8 inserted; record dengan timestamp sama tetap terbaca |
| Rerun pada cutoff yang sama | 2 extracted dalam lookback, 0 inserted, 2 duplicates; raw tetap 8 rows |
| Failure setelah raw insert sebelum checkpoint | Insert baru rollback; raw tetap 8 rows dan checkpoint lama tetap berlaku |
| Retry setelah failure tersebut | 1 versi baru tersimpan; raw menjadi 9 rows dan checkpoint maju |
| CLI | Berhasil menjalankan rerun dan mengeluarkan ringkasan JSON |

Verification lain:

- `python -m unittest discover -s tests -v`: **10/10 lulus**, terdiri dari
  3 integration tests dan 7 tests `OrderEvent` sebelumnya; tidak ada test skipped.
- `python scripts/validate_examples.py`: **5 contoh lulus**.
- `python -m compileall -q src scripts tests`: berhasil.
- `python -m pip check`: tidak ada dependency yang rusak.
- `git diff --check`: tidak ada whitespace error pada tracked diff.

Dependency yang digunakan saat verifikasi: SQLAlchemy 2.1.1, pandas 3.0.6,
psycopg 3.3.6, dan Python 3.11. Dependency dipasang ke `.venv` repository.
Connection contoh menggunakan `127.0.0.1` dan timeout 5 detik; penggunaan
`localhost` pada perangkat ini menyebabkan koneksi awal jauh lebih lambat.

Container uji sementara dibersihkan setelah pengujian. Tidak ada commit atau push
Git yang dilakukan.

## Cara mencoba

Ikuti bagian **Hari 2: incremental orders ingestion** di README untuk setup
database dan menjalankan migration serta seed. Setelah `POSTGRES_URL` tersedia:

```powershell
python scripts/run_incremental_orders.py --safe-cutoff '2026-09-28T10:20:00+07:00' --page-size 2
```

Run kedua dengan cutoff yang sama menghasilkan 0 insert baru pada dataset contoh.
Python tidak membaca `.env` otomatis; export `POSTGRES_URL` ke shell sesuai README.

## Batas implementasi yang perlu dipahami

- Jalankan satu pipeline pada satu waktu; concurrent-run locking belum diterapkan.
- Payload untuk pasangan `(order_id, version)` harus immutable. Source harus
  menaikkan version dan updated_at ketika data berubah.
- Hash conflict, quarantine, dan stale-version classification akan dibahas nanti.
- `safe_cutoff` diberikan manual; replica lag dan cutoff otomatis belum diukur.
- Source pada demo perlu stabil selama pagination; belum ada snapshot isolation
  untuk seluruh extraction.
- Snapshot ingestion hanya menyimpan versi yang sempat diobservasi.
- Lookback 15 menit bukan jaminan untuk keterlambatan yang melebihi window tersebut.

## Urutan membaca kode untuk belajar

Mulai dari `models.py`, kemudian `service.py` untuk melihat alur. Setelah itu baca
`repository.py`, terutama `fetch_order_page()` dan `finalize_run()`. Terakhir baca
test failure untuk melihat bukti bahwa raw write dan checkpoint bersifat atomic.
