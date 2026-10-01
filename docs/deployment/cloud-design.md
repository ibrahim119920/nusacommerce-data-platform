# Cloud migration design (belum dideploy)

## Target sederhana

```text
Application DB/API → private container ingestion jobs
                            |
             +--------------+-------------+
             |                            |
         S3 raw lake              warehouse PostgreSQL/RDS
         immutable prefixes                |
             |                            dbt → marts
         Spark batch
             |
         S3 derived

Scheduler/Airflow → task containers
Metrics/logs → monitoring + notification channel
Secrets Manager + task IAM role → runtime access, bukan key di Git
```

Pilihan AWS ini contoh desain, bukan rekomendasi biaya/layanan yang sudah diukur. Jangan menganggap semua managed services wajib untuk internship portfolio.

## Pemetaan dan keputusan

| Lokal | Kandidat cloud | Perubahan yang masih diperlukan |
|---|---|---|
| File Parquet volume | S3 object storage | Adapter exporter/reader S3; immutable prefixes + manifest publish; bukan os.replace |
| PostgreSQL Compose | RDS PostgreSQL private subnet | TLS, security groups, role terpisah source/raw/analytics, backup/restore |
| Container manual | VM/managed container jobs | Image registry, resource limits, task identity, retry contract |
| local[2] Spark | Managed Spark / cluster | Storage connector, distributed reads, tuning partitions/skew dan cost cap |
| Standalone Airflow SQLite | Airflow deployment terkelola/terpisah | Production metadata DB, workers, RBAC, secrets, capacity |
| Prometheus lokal | Metrics/log platform + alerts | Retention, auth, notification delivery, SLO |
| One Kafka broker | Managed/multi-broker Kafka | Replication, persistent log, IAM/TLS, retention, lag monitoring |

S3 menyimpan objects dalam buckets; file rename lokal tidak menjadi atomic rename object. Desain RDS menggunakan VPC dan security groups, tidak membuka database public. [S3 documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html), [RDS VPC documentation](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.html).

## Kapan memilih apa?

Untuk demo kecil: satu VM + container dapat lebih mudah dirawat, tetapi Anda mengelola failure/backup/patching sendiri. Managed services mengurangi beberapa pekerjaan operasional, tetapi tidak menghilangkan desain idempotency/quality dan biasanya menambah biaya serta dependency platform. Jangan memakai cluster Spark untuk 8 order hanya agar diagram terlihat kompleks.

## Gate sebelum deployment cloud

- Pilih account/region/budget secara eksplisit.
- Pisahkan test/demo/production dan credentials.
- Model least-privilege, TLS, network isolation dan retention PII.
- Uji S3 commit protocol serta distributed Spark, bukan hanya ganti path.
- Jalankan restore drill, tentukan RPO/RTO.
- Cost alarms, ownership, termination plan, security scan image/dependencies.
- Pastikan definisi freshness, availability dan quality dapat diukur.

Tidak ada resource AWS, tagihan, terraform apply, SSH deployment, atau secret cloud yang dibuat oleh implementasi ini.
