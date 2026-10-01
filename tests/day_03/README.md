# Hari 3: Payment API tests

Tulis test client kecil di folder ini. Target minimum:

1. HTTP 429 diikuti HTTP 200: request ulang memakai cursor yang sama.
2. Timeout atau HTTP 503 berhenti setelah batas attempt yang ditetapkan.
3. Response JSON dengan struktur yang salah ditolak.

Gunakan mock response dan patch `time.sleep` agar test tidak mengakses internet
atau menunggu jeda retry sungguhan.

Test integrasi PostgreSQL boleh ditambahkan setelah penyimpanan satu page selesai.
