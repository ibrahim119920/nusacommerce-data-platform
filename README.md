# NusaCommerce Data Platform

## Tujuan project

NusaCommerce Data Platform adalah fondasi untuk menerima, memvalidasi, dan
menyiapkan data event commerce sebelum diproses oleh pipeline data. Implementasi
saat ini berfokus pada kontrak data `OrderEvent` yang:

- mengubah payload menjadi model bertipe;
- memvalidasi aturan kontrak;
- menjaga model tetap immutable;
- memisahkan field tambahan ke `extra_fields`; dan
- menghasilkan record yang siap diserialisasi tanpa mencatat seluruh payload
  ketika validasi gagal.

Interface utamanya adalah:

```python
order_event = OrderEvent.from_dict(payload)
order_event.validate()
record = order_event.to_record()
```

## Requirement Python

- Python 3.10 atau lebih baru.
- `pip` dan modul standar `venv` untuk setup lokal.

Project tidak memerlukan API atau database untuk menjalankan validator dan test
saat ini.

## Setup environment

Dari root repository, buat dan aktifkan virtual environment.

PowerShell (Windows):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Bash (Linux/macOS):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## Menjalankan validator

Validator lokal membuktikan payload valid dapat diparsing, `campaign_id` masuk
ke `extra_fields`, serta naive datetime, version nol, dan currency lowercase
ditolak.

```shell
python scripts/validate_examples.py
```

Eksekusi yang berhasil berakhir dengan output:

```text
All local OrderEvent examples passed.
```

## Menjalankan test

Test menggunakan modul `unittest` dari standard library:

```shell
python -m unittest discover -s tests -v
```

## Struktur repository

```text
nusacommerce-data-platform/
|-- docs/
|   |-- adr/                  # Architecture Decision Records
|   `-- architecture/         # Ringkasan dan desain arsitektur
|-- scripts/
|   `-- validate_examples.py  # Validasi contoh kontrak secara lokal
|-- src/
|   `-- nusacommerce/
|       `-- domain/
|           `-- order_event.py # Model dan aturan kontrak OrderEvent
|-- tests/
|   `-- test_order_event.py   # Test kontrak OrderEvent
|-- .gitignore
|-- pyproject.toml            # Metadata package dan requirement Python
`-- README.md
```
