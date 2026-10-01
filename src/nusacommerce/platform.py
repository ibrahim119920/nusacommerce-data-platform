"""Local bootstrap and auditable blocking quality checks."""
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]


def bootstrap(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS control"))
        conn.execute(text("""CREATE TABLE IF NOT EXISTS control.schema_migrations (
            filename TEXT PRIMARY KEY, sha256 TEXT NOT NULL, applied_at TIMESTAMPTZ DEFAULT NOW())"""))
    for path in sorted((ROOT / "sql/migrations").glob("*.sql")):
        body = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(body.encode()).hexdigest()
        with engine.connect() as conn:
            old = conn.execute(text("SELECT sha256 FROM control.schema_migrations WHERE filename=:name"),
                               {"name": path.name}).scalar_one_or_none()
        if old:
            if old != digest:
                raise ValueError("applied_migration_changed_" + path.name)
            continue
        raw = engine.raw_connection()
        try:
            with raw.cursor() as cursor:
                cursor.execute(body)
                cursor.execute("INSERT INTO control.schema_migrations(filename,sha256) VALUES (%s,%s)",
                               (path.name, digest))
            raw.commit()
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.close()
    for name in ("day_02_orders.sql", "day_04_warehouse.sql"):
        raw = engine.raw_connection()
        try:
            with raw.cursor() as cursor:
                cursor.execute((ROOT / "sql/seeds" / name).read_text(encoding="utf-8"))
            raw.commit()
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.close()


QUALITY_CHECKS = {
    "orders_loaded": "SELECT CASE WHEN COUNT(*)>0 THEN 0 ELSE 1 END FROM warehouse.fct_orders",
    "customer_mapping": "SELECT COUNT(*) FROM warehouse.fct_orders WHERE customer_sk IS NULL",
    "orphan_payments": """SELECT COUNT(*) FROM warehouse.fct_payments p
        LEFT JOIN warehouse.fct_orders o USING(order_id) WHERE o.order_id IS NULL""",
    "finance_reconciliation": """SELECT CASE WHEN
        (SELECT COALESCE(SUM(net),0) FROM marts.daily_finance) =
        (SELECT COALESCE(SUM(amount),0) FROM warehouse.fct_payments WHERE status='succeeded') -
        (SELECT COALESCE(SUM(amount),0) FROM warehouse.fct_refunds) THEN 0 ELSE 1 END""",
    "negative_payment_amount": "SELECT COUNT(*) FROM warehouse.fct_payments WHERE amount<0",
}


def check_quality(engine):
    with engine.begin() as conn:
        results = {name: int(conn.execute(text(query)).scalar_one())
                   for name, query in QUALITY_CHECKS.items()}
        passed = all(value == 0 for value in results.values())
        conn.execute(text("""INSERT INTO control.quality_runs(run_id,results,passed)
            VALUES (:id,CAST(:results AS JSONB),:passed)"""),
            {"id": uuid4(), "results": json.dumps(results), "passed": passed})
    if not passed:
        raise ValueError("blocking_quality_failure_" + ",".join(k for k,v in results.items() if v))
    return results
