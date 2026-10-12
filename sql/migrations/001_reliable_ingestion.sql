CREATE SCHEMA IF NOT EXISTS source;
CREATE SCHEMA IF NOT EXISTS landing;
CREATE SCHEMA IF NOT EXISTS control;
CREATE SCHEMA IF NOT EXISTS quality;

-- Tabel simulasi database OLTP yang menyimpan kondisi order saat ini.
CREATE TABLE source.orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    status TEXT NOT NULL,
    amount NUMERIC(18, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL
        CHECK (currency ~ '^[A-Z]{3}$'),
    version INTEGER NOT NULL
        CHECK (version >= 1),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

-- Mempercepat pembacaan berdasarkan rentang updated_at dan urutan order_id.
CREATE INDEX source_orders_updated_at_order_id_idx
    ON source.orders (updated_at, order_id);

-- Satu baris untuk setiap eksekusi pipeline.
CREATE TABLE landing.ingestion_runs (
    run_id UUID PRIMARY KEY,
    pipeline_name TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('running', 'succeeded', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    extracted_count INTEGER NOT NULL DEFAULT 0
        CHECK (extracted_count >= 0),
    inserted_count INTEGER NOT NULL DEFAULT 0
        CHECK (inserted_count >= 0),
    duplicate_count INTEGER NOT NULL DEFAULT 0
        CHECK (duplicate_count >= 0),
    stale_count INTEGER NOT NULL DEFAULT 0
        CHECK (stale_count >= 0),
    conflict_count INTEGER NOT NULL DEFAULT 0
        CHECK (conflict_count >= 0),
    error_code TEXT,
    CHECK (window_start <= window_end),
    CHECK (
        (status = 'running' AND completed_at IS NULL)
        OR
        (status IN ('succeeded', 'failed') AND completed_at IS NOT NULL)
    ),
    UNIQUE (pipeline_name, run_id)
);

-- Menampung hasil extraction sementara, dengan satu baris per order dalam satu run.
CREATE TABLE landing.staged_orders (
    run_id UUID NOT NULL REFERENCES landing.ingestion_runs(run_id),
    order_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    source_updated_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL
        CHECK (jsonb_typeof(payload) = 'object'),
    payload_hash TEXT NOT NULL
        CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (run_id, order_id)
);

-- Menyimpan versi order yang benar-benar pernah diamati oleh pipeline.
CREATE TABLE landing.raw_order_versions (
    order_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    source_updated_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL
        CHECK (jsonb_typeof(payload) = 'object'),
    payload_hash TEXT NOT NULL
        CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    first_seen_run_id UUID NOT NULL
        REFERENCES landing.ingestion_runs(run_id),
    PRIMARY KEY (order_id, version)
);

-- Menyimpan kemajuan terakhir yang sudah berhasil diselesaikan untuk setiap pipeline.
CREATE TABLE control.ingestion_checkpoints (
    pipeline_name TEXT PRIMARY KEY,
    last_completed_window_end TIMESTAMPTZ,
    last_successful_run_id UUID,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (pipeline_name, last_successful_run_id)
        REFERENCES landing.ingestion_runs (pipeline_name, run_id),
    CHECK (
        (last_completed_window_end IS NULL AND last_successful_run_id IS NULL)
        OR
        (last_completed_window_end IS NOT NULL
         AND last_successful_run_id IS NOT NULL)
    )
);

-- Mencatat metadata konflik tanpa menyalin payload atau data pelanggan.
CREATE TABLE quality.order_conflicts (
    conflict_id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES landing.ingestion_runs(run_id),
    order_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    existing_payload_hash TEXT NOT NULL
        CHECK (existing_payload_hash ~ '^[0-9a-f]{64}$'),
    incoming_payload_hash TEXT NOT NULL
        CHECK (incoming_payload_hash ~ '^[0-9a-f]{64}$'),
    reason_code TEXT NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, order_id, version, incoming_payload_hash)
);
