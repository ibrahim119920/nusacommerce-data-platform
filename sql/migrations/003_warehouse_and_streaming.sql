ALTER TABLE landing.raw_payment_versions ADD COLUMN payload_hash TEXT;
CREATE TABLE landing.raw_customer_history (
 customer_id TEXT NOT NULL, city TEXT NOT NULL, membership TEXT NOT NULL,
 valid_from TIMESTAMPTZ NOT NULL, valid_to TIMESTAMPTZ,
 PRIMARY KEY(customer_id,valid_from), CHECK(valid_to IS NULL OR valid_to>valid_from)
);
CREATE TABLE landing.raw_products (
 product_id TEXT PRIMARY KEY, product_name TEXT NOT NULL, category TEXT NOT NULL,
 current_price NUMERIC(18,2) NOT NULL CHECK(current_price>=0)
);
CREATE TABLE landing.raw_order_items (
 order_id TEXT NOT NULL, line_number INTEGER NOT NULL,
 product_id TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>0),
 unit_price NUMERIC(18,2) NOT NULL CHECK(unit_price>=0), PRIMARY KEY(order_id,line_number)
);
CREATE TABLE landing.raw_refunds (
 refund_id TEXT PRIMARY KEY, order_id TEXT NOT NULL,
 amount NUMERIC(18,2) NOT NULL CHECK(amount>0), currency TEXT NOT NULL,
 refunded_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE landing.clickstream_events (
 event_id TEXT PRIMARY KEY, payload JSONB NOT NULL, payload_hash TEXT NOT NULL,
 topic TEXT NOT NULL, kafka_partition INTEGER NOT NULL, kafka_offset BIGINT NOT NULL,
 ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(topic,kafka_partition,kafka_offset)
);
CREATE TABLE control.quality_runs (
 run_id UUID PRIMARY KEY, checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 results JSONB NOT NULL, passed BOOLEAN NOT NULL
);
