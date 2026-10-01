-- Raw landing table for immutable payment versions from the Day 3 mock API.
CREATE TABLE IF NOT EXISTS landing.raw_payment_versions (
    payment_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    order_id TEXT NOT NULL,
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (payment_id, version)
);

CREATE INDEX IF NOT EXISTS raw_payment_versions_order_id_idx
    ON landing.raw_payment_versions (order_id);
