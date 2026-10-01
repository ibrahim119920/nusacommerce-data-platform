CREATE SCHEMA IF NOT EXISTS source;
CREATE SCHEMA IF NOT EXISTS landing;
CREATE SCHEMA IF NOT EXISTS control;
CREATE SCHEMA IF NOT EXISTS quality;

-- Tabel simulasi database OLTP yang menyimpan kondisi order saat ini.
CREATE TABLE source.orders (
    order_id TEXT PRIMARY KEY, -- Identitas unik order dari sistem sumber.
    customer_id TEXT NOT NULL, -- ID pelanggan yang membuat order.
    status TEXT NOT NULL, -- Status order saat ini, misalnya placed atau cancelled.
    amount NUMERIC(18, 2) NOT NULL, -- Nilai order dalam mata uang yang tercatat.
    currency VARCHAR(3) NOT NULL -- Kode mata uang tiga huruf kapital, misalnya IDR.
        CHECK (currency ~ '^[A-Z]{3}$'),
    version INTEGER NOT NULL -- Nomor versi sumber; harus naik saat order berubah.
        CHECK (version >= 1),
    created_at TIMESTAMPTZ NOT NULL, -- Waktu order pertama kali dibuat di sumber.
    updated_at TIMESTAMPTZ NOT NULL -- Waktu terakhir record berubah; dipakai untuk incremental extraction.
);

-- Mempercepat pembacaan berdasarkan rentang updated_at dan urutan order_id.
CREATE INDEX source_orders_updated_at_order_id_idx
    ON source.orders (updated_at, order_id);

-- Satu baris untuk setiap eksekusi pipeline.
CREATE TABLE landing.ingestion_runs (
    run_id UUID PRIMARY KEY, -- Identitas unik untuk satu eksekusi pipeline.
    pipeline_name TEXT NOT NULL, -- Nama pipeline, misalnya orders_incremental.
    window_start TIMESTAMPTZ NOT NULL, -- Batas awal updated_at yang dibaca oleh run ini.
    window_end TIMESTAMPTZ NOT NULL, -- Batas akhir window yang dibaca oleh run ini.
    status TEXT NOT NULL -- Status run selama siklus hidupnya.
        CHECK (status IN ('running', 'succeeded', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- Waktu mulai run.
    completed_at TIMESTAMPTZ, -- Waktu run selesai; NULL selama run masih berjalan.
    extracted_count INTEGER NOT NULL DEFAULT 0 -- Jumlah record yang berhasil diekstrak.
        CHECK (extracted_count >= 0),
    inserted_count INTEGER NOT NULL DEFAULT 0 -- Jumlah versi baru yang masuk ke tabel raw.
        CHECK (inserted_count >= 0),
    duplicate_count INTEGER NOT NULL DEFAULT 0 -- Jumlah payload identik yang ditemukan ulang.
        CHECK (duplicate_count >= 0),
    stale_count INTEGER NOT NULL DEFAULT 0 -- Jumlah versi yang lebih lama daripada versi yang sudah diketahui.
        CHECK (stale_count >= 0),
    conflict_count INTEGER NOT NULL DEFAULT 0 -- Jumlah konflik, misalnya key dan versi sama dengan payload berbeda.
        CHECK (conflict_count >= 0),
    error_code TEXT, -- Kode error aman untuk diagnosis; jangan simpan payload atau data sensitif di sini.
    CHECK (window_start <= window_end), -- Memastikan rentang waktu run valid.
    CHECK (
        (status = 'running' AND completed_at IS NULL)
        OR
        (status IN ('succeeded', 'failed') AND completed_at IS NOT NULL)
    ), -- Menjaga konsistensi antara status run dan waktu selesai.
    UNIQUE (pipeline_name, run_id) -- Memungkinkan referensi run yang juga memvalidasi nama pipeline.
);

-- Menampung hasil extraction sementara, dengan satu baris per order dalam satu run.
CREATE TABLE landing.staged_orders (
    run_id UUID NOT NULL REFERENCES landing.ingestion_runs(run_id), -- Run yang mengekstrak order ini.
    order_id TEXT NOT NULL, -- Identitas order dari sumber.
    version INTEGER NOT NULL CHECK (version >= 1), -- Versi order yang dibaca dari sumber.
    source_updated_at TIMESTAMPTZ NOT NULL, -- Nilai updated_at asli dari sumber.
    payload JSONB NOT NULL -- Isi order yang diekstrak, disimpan sebagai objek JSON.
        CHECK (jsonb_typeof(payload) = 'object'),
    payload_hash TEXT NOT NULL -- Hash payload canonical untuk membandingkan isi secara konsisten.
        CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (run_id, order_id) -- Mencegah order yang sama masuk dua kali dalam run yang sama.
);

-- Menyimpan versi order yang benar-benar pernah diamati oleh pipeline.
CREATE TABLE landing.raw_order_versions (
    order_id TEXT NOT NULL, -- Identitas order dari sistem sumber.
    version INTEGER NOT NULL CHECK (version >= 1), -- Nomor versi order yang diamati.
    source_updated_at TIMESTAMPTZ NOT NULL, -- Waktu perubahan menurut sistem sumber.
    payload JSONB NOT NULL -- Snapshot payload order yang diamati.
        CHECK (jsonb_typeof(payload) = 'object'),
    payload_hash TEXT NOT NULL -- Dipakai untuk membedakan duplicate identik dari konflik payload.
        CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- Waktu platform pertama kali menyimpan versi ini.
    first_seen_run_id UUID NOT NULL -- Run pertama yang berhasil mengamati versi ini.
        REFERENCES landing.ingestion_runs(run_id),
    PRIMARY KEY (order_id, version) -- Satu versi sumber hanya boleh tercatat satu kali.
);

-- Menyimpan kemajuan terakhir yang sudah berhasil diselesaikan untuk setiap pipeline.
CREATE TABLE control.ingestion_checkpoints (
    pipeline_name TEXT PRIMARY KEY, -- Nama pipeline yang checkpoint-nya disimpan.
    last_completed_window_end TIMESTAMPTZ, -- Akhir window terakhir yang selesai diproses; NULL berarti belum ada.
    last_successful_run_id UUID, -- Run terakhir yang berhasil menyelesaikan window tersebut.
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- Waktu record checkpoint terakhir diperbarui.
    FOREIGN KEY (pipeline_name, last_successful_run_id)
        REFERENCES landing.ingestion_runs (pipeline_name, run_id), -- Memastikan run sukses berasal dari pipeline yang sama.
    CHECK (
        (last_completed_window_end IS NULL AND last_successful_run_id IS NULL)
        OR
        (last_completed_window_end IS NOT NULL
         AND last_successful_run_id IS NOT NULL)
    ) -- Memastikan window selesai dan run sukses selalu dicatat berpasangan.
);

-- Mencatat metadata konflik tanpa menyalin payload atau data pelanggan.
CREATE TABLE quality.order_conflicts (
    conflict_id UUID PRIMARY KEY, -- Identitas unik untuk catatan konflik.
    run_id UUID NOT NULL REFERENCES landing.ingestion_runs(run_id), -- Run yang menemukan konflik.
    order_id TEXT NOT NULL, -- Order yang mengalami konflik.
    version INTEGER NOT NULL CHECK (version >= 1), -- Versi order yang konflik.
    existing_payload_hash TEXT NOT NULL -- Hash payload versi yang sudah tersimpan.
        CHECK (existing_payload_hash ~ '^[0-9a-f]{64}$'),
    incoming_payload_hash TEXT NOT NULL -- Hash payload baru yang berbeda dari versi tersimpan.
        CHECK (incoming_payload_hash ~ '^[0-9a-f]{64}$'),
    reason_code TEXT NOT NULL, -- Kode yang menjelaskan jenis konflik.
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- Waktu konflik ditemukan.
    UNIQUE (run_id, order_id, version, incoming_payload_hash) -- Mencegah konflik yang sama dicatat berulang dalam satu run.
);