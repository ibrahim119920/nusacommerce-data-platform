# Local operations runbook

## Check cepat

```powershell
docker compose --profile tools run --rm app monitor
Invoke-RestMethod http://localhost:8014/health
docker compose --profile tools run --rm app summary
docker compose --profile monitoring logs --tail 30 metrics prometheus
```

/health: 200 healthy, 503 gagal. Prometheus http://localhost:9094/alerts menampilkan pending/firing sesuai for-duration. Aturan alert belum mengirim notifikasi external.

Tabel run sebenarnya adalah **landing.ingestion_runs**, checkpoint **control.ingestion_checkpoints**, bukan control.ingestion_runs/pipeline_checkpoints yang sempat disebut pada README tahap sebelumnya.

## Failure dan tindakan

| Gejala | Diagnosis aman | Recovery |
|---|---|---|
| HTTP429/503 | Bounded retry logs, jangan log token/payload | Tunggu sumber pulih; rerun payments; jangan unlimited retry |
| Orders failed sebelum finalize | Run status, checkpoint terakhir | Rerun cutoff sama/lebih baru; tidak menghapus raw/checkpoint |
| Same ID/version hash berbeda | quality.order_conflicts | Periksa source contract; jangan auto-skip/update data mentah |
| Quality failed | control.quality_runs, dbt run_results | Perbaiki source/transform, build + test ulang; hentikan konsumsi laporan |
| Snapshot export terputus | latest.json masih menunjuk snapshot sebelumnya | Rerun export; .snapshot-*.tmp tidak dipakai reader |
| Spark gagal | Snapshot manifest/checksum, memory dan log Spark | Rerun snapshot_id yang sama; raw tidak berubah |
| Ingestion stale | /health reasons, scheduler/DAG paused | Pulihkan scheduling dan run sukses; jangan memalsukan timestamp |
| Kafka replay | received/duplicates, offset state | Rerun consumer; same event_id immutable wajib |
| Broker recreate | Topic/offset hilang, raw DB masih ada | Demo publish ulang fixture; untuk data baru desain persistent log + replay identity |
| Task running lama | started_at, process/DAG status | Konfirmasi proses mati sebelum intervensi; jangan truncate tabel untuk concurrency |

## Backfill

```powershell
docker compose --profile tools run --rm app backfill --start '2026-09-28T00:00:00+07:00' --cutoff '2026-09-29T00:00:00+07:00'
docker compose --profile tools run --rm app dbt
docker compose --profile tools run --rm app quality
```

Backfill tidak memundurkan checkpoint. Pada source current-state, backfill membaca versi yang masih ada di source sekarang; ini **bukan** pemulihan perubahan historis yang tidak pernah disimpan.

## Backup, restore, rollback

Demo: simpan pg_dump database reference dan salin volume artifacts saat tidak ada penulis. Dump data yang punya PII harus ditangani sebagai data sensitif. Restore ke database/container baru terlebih dahulu; jalankan quality dan reconciliation sebelum mengganti target. Restore drill belum dijalankan dalam report ini.

Rollback deployment: tag image dengan commit SHA, simpan image sebelumnya, hentikan scheduling, pilih image lama, lalu validasi. Migration yang sudah diterapkan jangan diedit; tambah migration baru. Rollback code tidak otomatis membalik migration/data. Jangan gunakan docker compose down -v.

## Stop / cleanup

```powershell
docker compose --profile streaming --profile monitoring --profile orchestration stop
```

Volumes PostgreSQL dan artifacts tetap ada. Snapshot/derived runs akan bertambah pada tiap run. Retention cleanup belum otomatis; untuk latihan hapus hanya snapshot yang tidak digunakan setelah memverifikasi path/backup, bukan seluruh workspace.
