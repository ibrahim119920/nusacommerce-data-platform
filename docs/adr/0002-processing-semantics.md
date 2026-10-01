# ADR-0002: Processing semantics

Status: Accepted for the Day 2 local exercise

## Decision

Pipeline berjalan secara berurutan dengan satu runner. Source berupa tabel
`source.orders` lokal, bukan read replica sebenarnya. `safe_cutoff` diberikan
oleh pemanggil dan tidak berubah selama pagination. Batas window adalah
`start <= updated_at < end`.

Run pertama dimulai dari 2026-01-01 UTC. Run berikutnya membaca ulang 15 menit
sebelum checkpoint. Cursor `(updated_at, order_id)` bergerak per page. Checkpoint
menyimpan akhir window yang selesai, termasuk ketika tidak ada record.

Setiap page disimpan ke staging dengan run ID baru. Finalisasi memasukkan raw
versions, memperbarui checkpoint, dan menandai run sukses dalam satu transaction.
Kegagalan sebelum commit membatalkan seluruh finalisasi; staging tetap tersedia.
Run gagal dicatat dalam transaction terpisah. Retry menggunakan run ID baru.

Primary key raw `(order_id, version)` mencegah duplikasi pada replay. Implementasi
memakai `ON CONFLICT DO NOTHING` dengan asumsi payload pada key tersebut immutable.
Count `duplicates` berarti key versi yang sudah tersimpan, bukan bukti bahwa
hash payload sudah dibandingkan.

## Batas latihan

- Producer wajib menaikkan version dan updated_at saat payload berubah.
- Tidak ada hash-conflict quarantine, stale-version classification, atau lock
  untuk concurrent runs pada tahap ini. Tabel quality tersedia untuk modul nanti.
- Source harus stabil selama pagination pada demo ini. Snapshot consistency,
  replica lag, dan cutoff otomatis akan dibahas pada tahap reliability.
- Lookback hanya menjangkau perubahan yang masih berada dalam window overlap.
- Incremental snapshot tidak menangkap semua intermediate changes.

## Verification

Integration tests menggunakan PostgreSQL terpisah dengan nama database berakhiran
`_test`: initial load, rerun, serta failure setelah raw insert sebelum checkpoint
yang harus rollback dan kemudian berhasil ketika di-retry.
