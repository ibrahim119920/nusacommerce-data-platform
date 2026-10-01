# ADR-0004: Capstone reference sampai Hari 14

Status: accepted untuk portfolio demo lokal.

## Keputusan

Lengkapi copy yang sama dengan local Parquet snapshots, Spark batch, operational health,
Prometheus alert rules, CI/release workflow, local deployment dan portfolio documentation.
Pertahankan folder/project name lama agar path dan volume tidak berpindah.

Data lake berisi raw observed versions; Spark derived mart tidak menggantikan finance dbt.
Pin snapshot_id pada DAG menggunakan XCom dan pada CLI capstone menggunakan hasil export.
Pisahkan venv Airflow dan app; gunakan GHCR Python base terverifikasi karena Docker Hub gagal
pada host ini. Cloud deployment hanya desain; tidak membuat resource berbayar.

## Tradeoff / batasan

Exporter fetch-all dan full snapshot cocok dataset course, bukan skala produksi.
local[2] tidak membuktikan distributed multi-host. SHA checksum bukan autentikasi
manifest terhadap penyerang yang dapat menulis keduanya. Quality gate bukan atomic
warehouse publication. Prometheus rules tidak memasang notification channel.

Direct dependencies dan base image dipin; seluruh transitive dependencies belum memiliki
lock/hash file lengkap. Workflow hosted dan publish belum dijalankan; lokal CI-equivalent
dan deployment diperiksa dalam verification report.
