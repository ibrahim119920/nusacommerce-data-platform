"""SQL operations for the single-runner Day 2 ingestion exercise."""

from datetime import datetime
from contextlib import contextmanager
import hashlib
from uuid import UUID
from uuid import uuid4

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from .hashing import canonical_payload_json, hash_payload
from .models import ExtractionWindow


class OrderIngestionRepository:
    """Keep database access separate from the order of pipeline steps."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def pipeline_lock(self, pipeline_name):
        """Keep one PostgreSQL session lock for the whole run."""
        key = int.from_bytes(hashlib.sha256(pipeline_name.encode()).digest()[:8], "big") >> 1
        with self.engine.connect() as connection:
            acquired = connection.execute(text("SELECT pg_try_advisory_lock(:key)"),
                                          {"key": key}).scalar_one()
            connection.commit()
            if not acquired:
                raise RuntimeError("pipeline_already_running")
            try:
                yield
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
                connection.commit()

    def check_conflicts(self, run_id):
        """Persist conflict metadata before raising; do not publish this batch."""
        with self.engine.begin() as connection:
            conflicts = connection.execute(text("""
                SELECT s.order_id,s.version,r.payload_hash AS old_hash,s.payload_hash AS new_hash
                FROM landing.staged_orders s JOIN landing.raw_order_versions r
                  ON s.order_id=r.order_id AND s.version=r.version
                WHERE s.run_id=:run_id AND s.payload_hash<>r.payload_hash
            """), {"run_id": run_id}).mappings().all()
            for row in conflicts:
                connection.execute(text("""
                    INSERT INTO quality.order_conflicts
                      (conflict_id,run_id,order_id,version,existing_payload_hash,incoming_payload_hash,reason_code)
                    VALUES (:id,:run_id,:order_id,:version,:old_hash,:new_hash,'same_version_different_payload')
                    ON CONFLICT DO NOTHING
                """), dict(row, id=uuid4(), run_id=run_id))
            if conflicts:
                connection.execute(text("UPDATE landing.ingestion_runs SET conflict_count=:count WHERE run_id=:id"),
                                   {"count": len(conflicts), "id": run_id})
        if conflicts:
            raise ValueError("order_version_payload_conflict")

    def load_checkpoint(self, pipeline_name: str) -> datetime | None:
        with self.engine.connect() as connection:
            return connection.execute(
                text("""
                    SELECT last_completed_window_end
                    FROM control.ingestion_checkpoints
                    WHERE pipeline_name = :pipeline_name
                """),
                {"pipeline_name": pipeline_name},
            ).scalar_one_or_none()

    def create_run(
        self, run_id: UUID, pipeline_name: str, window: ExtractionWindow
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO landing.ingestion_runs
                        (run_id, pipeline_name, window_start, window_end, status)
                    VALUES (:run_id, :pipeline_name, :start, :end, 'running')
                """),
                {"run_id": run_id, "pipeline_name": pipeline_name,
                 "start": window.start, "end": window.end},
            )

    def fetch_order_page(
        self,
        window: ExtractionWindow,
        limit: int,
        last_updated_at: datetime | None = None,
        last_order_id: str | None = None,
    ) -> pd.DataFrame:
        if limit < 1:
            raise ValueError("Page size must be positive")
        if (last_updated_at is None) != (last_order_id is None):
            raise ValueError("Both cursor fields must be supplied together")

        # Only this fixed SQL fragment changes; source values stay parameterized.
        cursor_clause = ""
        params = {"start": window.start, "end": window.end, "limit": limit}
        if last_updated_at is not None:
            cursor_clause = (
                "AND (updated_at, order_id) > (:last_updated_at, :last_order_id)"
            )
            params.update(last_updated_at=last_updated_at, last_order_id=last_order_id)
        query = text("""
            SELECT order_id, customer_id, status, amount, currency,
                   version, created_at, updated_at
            FROM source.orders
            WHERE updated_at >= :start AND updated_at < :end
        """ + cursor_clause + " ORDER BY updated_at, order_id LIMIT :limit")
        with self.engine.connect() as connection:
            result = connection.execute(query, params)
            return pd.DataFrame(result.fetchall(), columns=result.keys())

    def stage_page(self, run_id: UUID, page: pd.DataFrame) -> int:
        """Commit one staging page; raw data and checkpoint remain unchanged."""
        if page.empty:
            return 0
        required = {"order_id", "version", "updated_at"}
        if not required.issubset(page.columns):
            raise ValueError("Page is missing required order metadata")
        if page[list(required)].isna().any().any():
            raise ValueError("Page contains NULL order metadata")
        if page["order_id"].duplicated().any():
            raise ValueError("Page contains duplicate order IDs")

        rows = [
            {"run_id": run_id, "order_id": payload["order_id"],
             "version": payload["version"], "updated_at": payload["updated_at"],
             "payload": canonical_payload_json(payload),
             "payload_hash": hash_payload(payload)}
            for payload in page.to_dict(orient="records")
        ]
        with self.engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO landing.staged_orders
                    (run_id, order_id, version, source_updated_at, payload, payload_hash)
                VALUES (:run_id, :order_id, :version, :updated_at,
                        CAST(:payload AS JSONB), :payload_hash)
            """), rows)
        return len(rows)

    def finalize_run(
        self, run_id: UUID, pipeline_name: str, window: ExtractionWindow,
        extracted: int, *, advance_checkpoint: bool = True,
    ) -> int:
        """Publish raw data, checkpoint, and successful status atomically.

        The run lock serializes order writers. Same-version hash conflicts
        block publication; backfill never advances the regular checkpoint.
        """
        self.check_conflicts(run_id)
        with self.engine.begin() as connection:
            inserted = connection.execute(text("""
                WITH inserted AS (
                    INSERT INTO landing.raw_order_versions
                        (order_id, version, source_updated_at, payload,
                         payload_hash, first_seen_run_id)
                    SELECT order_id, version, source_updated_at, payload,
                           payload_hash, run_id
                    FROM landing.staged_orders WHERE run_id = :run_id
                    ON CONFLICT (order_id, version) DO NOTHING
                    RETURNING 1
                )
                SELECT COUNT(*) FROM inserted
            """), {"run_id": run_id}).scalar_one()
            if advance_checkpoint:
                self._advance_checkpoint(connection, pipeline_name, run_id, window.end)
            connection.execute(text("""
                UPDATE landing.ingestion_runs
                SET status = 'succeeded', completed_at = NOW(),
                    extracted_count = :extracted, inserted_count = :inserted,
                    duplicate_count = :duplicates
                WHERE run_id = :run_id
            """), {"run_id": run_id, "extracted": extracted,
                   "inserted": inserted, "duplicates": extracted - inserted})
        return inserted

    def _advance_checkpoint(
        self, connection: Connection, pipeline_name: str,
        run_id: UUID, window_end: datetime,
    ) -> None:
        connection.execute(text("""
            INSERT INTO control.ingestion_checkpoints
                (pipeline_name, last_completed_window_end, last_successful_run_id)
            VALUES (:pipeline_name, :end, :run_id)
            ON CONFLICT (pipeline_name) DO UPDATE
            SET last_completed_window_end = EXCLUDED.last_completed_window_end,
                last_successful_run_id = EXCLUDED.last_successful_run_id,
                updated_at = NOW()
        """), {"pipeline_name": pipeline_name, "end": window_end, "run_id": run_id})

    def mark_run_failed(self, run_id: UUID, extracted: int, error_code: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("""
                UPDATE landing.ingestion_runs
                SET status = 'failed', completed_at = NOW(),
                    extracted_count = :extracted, error_code = :error_code
                WHERE run_id = :run_id AND status = 'running'
            """), {"run_id": run_id, "extracted": extracted, "error_code": error_code})
