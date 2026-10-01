# Hari 3: Payment API ingestion

## Tujuan

Ambil enam pembayaran dari mock API lokal, simpan ke PostgreSQL, lalu jalankan
pipeline kembali tanpa membuat row raw duplikat.

## Urutan kerja

1. Pasang dependency project dengan `python -m pip install -e .`.
2. Jalankan `python scripts/mock_payment_api.py` di terminal pertama.
3. Jalankan migration `sql/migrations/002_payment_ingestion.sql` pada database
   NusaCommerce yang sudah dipakai untuk Hari 2.
4. Lengkapi `PaymentApiClient.fetch_page()` untuk timeout, retry terbatas,
   `Retry-After`, status HTTP, dan bentuk JSON response.
5. Lengkapi `PaymentRepository.insert_page()` untuk menyimpan satu page dalam
   transaction dan menangani rerun dengan primary key `(payment_id, version)`.
6. Lengkapi `PaymentIngestionService.run()` untuk mengambil page sampai
   `next_cursor` bernilai `None`.
7. Lengkapi `scripts/run_payment_ingestion.py` agar menjalankan rangkaian tersebut.
8. Tulis tiga test minimum yang dicatat di `tests/day_03/README.md`.

## Aturan latihan

- Cursor diteruskan kembali seperti yang diberikan API.
- Jika penyimpanan page gagal, hentikan run sebelum bergerak ke cursor berikutnya.
- Gunakan maksimal tiga attempt per request.
- Simpan nominal pembayaran sebagai decimal/string atau JSON angka desimal yang
  konsisten; jangan mengubahnya menjadi Python `float` untuk perhitungan uang.
- Fixture mock berisi data sintetis dan sengaja memberi satu HTTP 429 pada page
  kedua. Restart mock server untuk mengulang simulasi 429.

## Kriteria selesai

- Run pertama memasukkan enam payment version.
- Response 429 berhasil dicoba ulang.
- Run kedua tidak menambah row duplikat.
- Test retry tidak memakai jaringan publik dan tidak menunggu delay nyata.

Setelah selesai, tambahkan cara menjalankan Payment API dan pipeline ke README.
