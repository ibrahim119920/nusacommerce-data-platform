-- Deterministic local seed for the Day 2 incremental-ingestion exercise.
-- Run this after migration 001 and before the first pipeline run.
-- This seeds the simulated source and an empty checkpoint. Run tables,
-- staging, raw versions, and quality conflicts should be written by the pipeline.

BEGIN;

INSERT INTO source.orders (
    order_id,
    customer_id,
    status,
    amount,
    currency,
    version,
    created_at,
    updated_at
)
VALUES
    (
        'ord-1001', 'cust-001', 'paid', 125000.00, 'IDR', 1,
        TIMESTAMPTZ '2026-09-27 08:00:00+07:00',
        TIMESTAMPTZ '2026-09-27 08:00:00+07:00'
    ),
    (
        'ord-1002', 'cust-002', 'processing', 250000.00, 'IDR', 1,
        TIMESTAMPTZ '2026-09-27 08:10:00+07:00',
        TIMESTAMPTZ '2026-09-28 09:00:00+07:00'
    ),
    (
        'ord-1003', 'cust-001', 'paid', 89000.00, 'IDR', 1,
        TIMESTAMPTZ '2026-09-27 08:20:00+07:00',
        TIMESTAMPTZ '2026-09-28 09:00:00+07:00'
    ),
    (
        'ord-1004', 'cust-003', 'cancelled', 175000.00, 'IDR', 1,
        TIMESTAMPTZ '2026-09-28 09:05:00+07:00',
        TIMESTAMPTZ '2026-09-28 09:15:00+07:00'
    ),
    (
        'ord-1005', 'cust-004', 'processing', 310000.00, 'IDR', 1,
        TIMESTAMPTZ '2026-09-28 09:30:00+07:00',
        TIMESTAMPTZ '2026-09-28 09:45:00+07:00'
    ),
    (
        'ord-1006', 'cust-002', 'paid', 0.00, 'IDR', 1,
        TIMESTAMPTZ '2026-09-28 09:50:00+07:00',
        TIMESTAMPTZ '2026-09-28 10:00:00+07:00'
    ),
    (
        'ord-1007', 'cust-005', 'shipped', 499000.00, 'IDR', 1,
        TIMESTAMPTZ '2026-09-28 10:05:00+07:00',
        TIMESTAMPTZ '2026-09-28 10:05:00+07:00'
    ),
    (
        'ord-1008', 'cust-003', 'paid', 72000.00, 'IDR', 1,
        TIMESTAMPTZ '2026-09-28 10:15:00+07:00',
        TIMESTAMPTZ '2026-09-28 10:15:00+07:00'
    )
ON CONFLICT (order_id) DO NOTHING;

-- A NULL checkpoint means this pipeline has not completed any window yet.
-- Replace the name only if the pipeline code uses another pipeline_name.
INSERT INTO control.ingestion_checkpoints (pipeline_name)
VALUES ('orders_incremental')
ON CONFLICT (pipeline_name) DO NOTHING;

COMMIT;

-- Test scenarios (run manually after the initial ingestion succeeds):

-- 1. Valid source update: version increases and updated_at advances.
-- This should create a new row in landing.raw_order_versions.
-- UPDATE source.orders
-- SET status = 'paid',
--     version = 2,
--     updated_at = TIMESTAMPTZ '2026-09-29 09:00:00+07:00'
-- WHERE order_id = 'ord-1005' AND version = 1;

-- 2. Contract violation: payload changes but version does not increase.
-- Conflict detection is deferred to a later module. Day 2 assumes immutable
-- payloads per (order_id, version); reusing a version violates that assumption.
-- Run only after version 1 of ord-1006 is present in landing.raw_order_versions.
-- UPDATE source.orders
-- SET amount = amount + 1000.00,
--     updated_at = TIMESTAMPTZ '2026-09-29 09:15:00+07:00'
-- WHERE order_id = 'ord-1006' AND version = 1;
