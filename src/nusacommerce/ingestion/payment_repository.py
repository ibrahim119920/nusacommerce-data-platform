"""Validate and store a payment page atomically."""
from decimal import Decimal, InvalidOperation
from datetime import datetime
from sqlalchemy import text
from .hashing import canonical_payload_json, hash_payload


class PaymentRepository:
    def __init__(self, engine):
        self.engine = engine

    def insert_page(self, payments):
        rows = []
        for payment in payments:
            try:
                for field in ("payment_id", "order_id"):
                    if not isinstance(payment[field], str) or not payment[field].strip():
                        raise ValueError()
                version = payment["version"]
                if isinstance(version, bool) or not isinstance(version, int) or version < 1:
                    raise ValueError()
                amount = Decimal(str(payment["amount"]))
                if not amount.is_finite() or amount < 0:
                    raise ValueError()
                if payment["currency"] != "IDR" or payment["status"] != "succeeded":
                    raise ValueError()
                timestamp = datetime.fromisoformat(payment["updated_at"])
                if timestamp.utcoffset() is None:
                    raise ValueError()
            except (KeyError, ValueError, TypeError, InvalidOperation):
                raise ValueError("invalid_payment_contract") from None
            rows.append({"id": payment["payment_id"], "version": version,
                "order": payment["order_id"], "payload": canonical_payload_json(payment),
                "hash": hash_payload(payment)})
        inserted = 0
        with self.engine.begin() as connection:
            for row in rows:
                existing = connection.execute(text("""
                    SELECT payload_hash FROM landing.raw_payment_versions
                    WHERE payment_id=:id AND version=:version
                """), row).scalar_one_or_none()
                if existing is not None and existing != row["hash"]:
                    raise ValueError("payment_version_payload_conflict")
                inserted += len(connection.execute(text("""
                    INSERT INTO landing.raw_payment_versions
                      (payment_id,version,order_id,payload,payload_hash)
                    VALUES (:id,:version,:order,CAST(:payload AS JSONB),:hash)
                    ON CONFLICT (payment_id,version) DO NOTHING RETURNING payment_id
                """), row).fetchall())
        return inserted
