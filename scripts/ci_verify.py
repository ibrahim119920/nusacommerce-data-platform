"""Run the reference checks without relying on a GitHub runner.

POSTGRES_URL is a fresh demo/CI database; TEST_POSTGRES_URL must be a separate
*_test database. The caller must provision both databases and Java/PySpark.
"""

import json
import os
import socket
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from nusacommerce.lake.snapshot import load_snapshot
from nusacommerce.platform import bootstrap

ROOT = Path(__file__).resolve().parents[1]


def run(*command, env):
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def main():
    env = os.environ.copy()
    demo_url = env["POSTGRES_URL"]
    test_url = env["TEST_POSTGRES_URL"]
    demo = make_url(demo_url)
    test = make_url(test_url)
    if not (test.database or "").endswith("_test") or test.database == demo.database:
        raise ValueError("Use separate demo and *_test databases")
    if (demo.database or "").endswith("_test"):
        raise ValueError("The capstone demo database must not be the test database")
    test_engine = create_engine(test_url)
    try:
        bootstrap(test_engine)
    finally:
        test_engine.dispose()
    env["RUN_SPARK_TESTS"] = "1"
    run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v", env=env)
    port = int(env.get("CI_PAYMENT_PORT", "18014"))
    env["PAYMENT_PORT"] = str(port)
    env["PAYMENT_API_URL"] = f"http://127.0.0.1:{port}"
    env["LAKE_ROOT"] = str(ROOT / "artifacts/ci/lake")
    mock = subprocess.Popen(
        [sys.executable, "scripts/mock_payment_api.py"], cwd=ROOT, env=env
    )
    try:
        for _ in range(100):
            if mock.poll() is not None:
                raise RuntimeError("mock_api_exited")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("mock_api_not_ready")
        run(
            sys.executable,
            "-m",
            "nusacommerce.cli",
            "capstone",
            "--cutoff",
            env.get("DEMO_CUTOFF", "2026-10-02T00:00:00+00:00"),
            env=env,
        )
    finally:
        mock.terminate()
        try:
            mock.wait(timeout=5)
        except subprocess.TimeoutExpired:
            mock.kill()
            mock.wait()
    root = Path(env["LAKE_ROOT"])
    _, manifest = load_snapshot(root)
    reports = list((root / "derived" / manifest["snapshot_id"]).glob("*/report.json"))
    if len(reports) != 1:
        raise AssertionError("Expected one derived run for the fresh snapshot")
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    engine = create_engine(demo_url)
    try:
        with engine.connect() as conn:
            expected = [
                dict(row)
                for row in conn.execute(
                    text("""
                SELECT order_date::text AS event_date,currency,COUNT(*) AS order_count,
                SUM(amount) AS order_value FROM warehouse.fct_orders
                WHERE status!='cancelled' GROUP BY order_date,currency
                ORDER BY order_date,currency
            """)
                ).mappings()
            ]
        actual = report["daily_orders"]
        normalized = lambda rows: [
            (
                row["event_date"],
                row["currency"],
                row["order_count"],
                Decimal(row["order_value"]),
            )
            for row in rows
        ]
        if normalized(actual) != normalized(expected):
            raise AssertionError("Spark and warehouse aggregates do not reconcile")
    finally:
        engine.dispose()
    print("CI_VERIFY_OK: unit/integration + capstone + Spark/warehouse parity")


if __name__ == "__main__":
    main()
