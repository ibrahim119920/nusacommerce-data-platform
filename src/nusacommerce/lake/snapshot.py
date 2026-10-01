"""Publish complete Parquet snapshots before updating the latest pointer.

A PostgreSQL REPEATABLE READ transaction provides one consistent raw snapshot.
The implementation materializes fixture-sized tables in memory; a large exporter
would stream batches rather than fetch all rows.
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import text

SNAPSHOT_NAME = re.compile(r"snapshot-[0-9a-f]{32}")
SCHEMAS = {
    "orders": pa.schema(
        [
            ("order_id", pa.string()),
            ("version", pa.int64()),
            ("customer_id", pa.string()),
            ("status", pa.string()),
            ("amount", pa.decimal128(18, 2)),
            ("currency", pa.string()),
            ("created_at", pa.timestamp("us", tz="UTC")),
            ("updated_at", pa.timestamp("us", tz="UTC")),
            ("event_date", pa.date32()),
        ]
    ),
    "payments": pa.schema(
        [
            ("payment_id", pa.string()),
            ("version", pa.int64()),
            ("order_id", pa.string()),
            ("amount", pa.decimal128(18, 2)),
            ("currency", pa.string()),
            ("status", pa.string()),
            ("updated_at", pa.timestamp("us", tz="UTC")),
            ("event_date", pa.date32()),
        ]
    ),
    "clickstream": pa.schema(
        [
            ("event_id", pa.string()),
            ("customer_id", pa.string()),
            ("event_type", pa.string()),
            ("event_time", pa.timestamp("us", tz="UTC")),
            ("event_date", pa.date32()),
        ]
    ),
}
QUERIES = {
    "orders": """
        SELECT order_id,version,payload->>'customer_id' AS customer_id,
        payload->>'status' AS status,(payload->>'amount')::numeric(18,2) AS amount,
        payload->>'currency' AS currency,
        (payload->>'created_at')::timestamptz AS created_at,
        source_updated_at AS updated_at,
        ((payload->>'created_at')::timestamptz AT TIME ZONE 'Asia/Jakarta')::date AS event_date
        FROM landing.raw_order_versions ORDER BY order_id,version
    """,
    "payments": """
        SELECT payment_id,version,payload->>'order_id' AS order_id,
        (payload->>'amount')::numeric(18,2) AS amount,payload->>'currency' AS currency,
        payload->>'status' AS status,(payload->>'updated_at')::timestamptz AS updated_at,
        ((payload->>'updated_at')::timestamptz AT TIME ZONE 'Asia/Jakarta')::date AS event_date
        FROM landing.raw_payment_versions ORDER BY payment_id,version
    """,
    "clickstream": """
        SELECT event_id,payload->>'customer_id' AS customer_id,
        payload->>'event_type' AS event_type,
        (payload->>'event_time')::timestamptz AS event_time,
        ((payload->>'event_time')::timestamptz AT TIME ZONE 'Asia/Jakarta')::date AS event_date
        FROM landing.clickstream_events ORDER BY event_id
    """,
}


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def export_snapshot(engine, lake_root: Path) -> dict:
    """Export all observed raw versions; do not overwrite a published snapshot."""
    lake_root = Path(lake_root)
    lake_root.mkdir(parents=True, exist_ok=True)
    snapshot_id = "snapshot-" + uuid4().hex
    temporary = lake_root / ("." + snapshot_id + ".tmp")
    temporary.mkdir()
    manifest = {
        "format_version": 1,
        "snapshot_id": snapshot_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "timezone": "Asia/Jakarta",
        "tables": {},
    }
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        with conn.begin():
            for name, query in QUERIES.items():
                rows = [dict(row) for row in conn.execute(text(query)).mappings()]
                if name == "orders" and not rows:
                    raise ValueError("lake_export_requires_orders")
                table = pa.Table.from_pylist(rows, schema=SCHEMAS[name])
                destination = temporary / name
                destination.mkdir()
                if rows:
                    pq.write_to_dataset(
                        table,
                        root_path=destination,
                        partition_cols=["event_date"],
                        compression="snappy",
                    )
                else:
                    pq.write_table(
                        table, destination / "empty.parquet", compression="snappy"
                    )
                entries = [
                    {
                        "path": str(path.relative_to(temporary)).replace("\\", "/"),
                        "sha256": file_digest(path),
                        "bytes": path.stat().st_size,
                    }
                    for path in sorted(destination.rglob("*.parquet"))
                ]
                manifest["tables"][name] = {"rows": len(rows), "files": entries}
    (temporary / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    os.replace(temporary, lake_root / snapshot_id)
    pointer = lake_root / (".latest-" + uuid4().hex + ".tmp")
    pointer.write_text(json.dumps({"snapshot_id": snapshot_id}), encoding="utf-8")
    os.replace(pointer, lake_root / "latest.json")
    return manifest


def load_snapshot(lake_root: Path, snapshot_id: str | None = None) -> tuple[Path, dict]:
    """Reject partial snapshots, unsafe paths, and damaged data before Spark reads."""
    root = Path(lake_root).resolve()
    if snapshot_id is None:
        snapshot_id = json.loads((root / "latest.json").read_text(encoding="utf-8"))[
            "snapshot_id"
        ]
    if not isinstance(snapshot_id, str) or not SNAPSHOT_NAME.fullmatch(snapshot_id):
        raise ValueError("invalid_snapshot_id")
    directory = (root / snapshot_id).resolve()
    if not directory.is_relative_to(root):
        raise ValueError("unsafe_snapshot_path")
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("format_version") != 1
        or manifest.get("snapshot_id") != snapshot_id
        or set(manifest.get("tables", {})) != set(SCHEMAS)
    ):
        raise ValueError("invalid_snapshot_manifest")
    for metadata in manifest["tables"].values():
        row_count = 0
        if not metadata["files"]:
            raise ValueError("missing_parquet_files")
        for entry in metadata["files"]:
            path = (directory / entry["path"]).resolve()
            if not path.is_relative_to(directory) or path.suffix != ".parquet":
                raise ValueError("unsafe_parquet_path")
            if (
                path.stat().st_size != entry["bytes"]
                or file_digest(path) != entry["sha256"]
            ):
                raise ValueError("parquet_checksum_mismatch")
            row_count += pq.ParquetFile(path).metadata.num_rows
        if row_count != metadata["rows"]:
            raise ValueError("parquet_row_count_mismatch")
    return directory, manifest
