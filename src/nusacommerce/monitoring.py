"""Read-only operational metrics and a localhost-oriented health exporter."""

import json
import logging
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from sqlalchemy import text

logger = logging.getLogger(__name__)


def collect_health(
    engine, *, max_age_seconds: int = 86400, now: datetime | None = None
) -> dict:
    if max_age_seconds < 1:
        raise ValueError("max_age_seconds must be positive")
    now = now or datetime.now(timezone.utc)
    if now.utcoffset() is None:
        raise ValueError("now must be timezone aware")
    with engine.connect() as conn:
        # Backfills do not satisfy freshness of scheduled ingestion.
        last = (
            conn.execute(
                text("""
            SELECT r.status,r.completed_at FROM landing.ingestion_runs r
            JOIN control.ingestion_checkpoints c
            ON c.last_successful_run_id=r.run_id
            WHERE c.pipeline_name='orders_incremental'
        """)
            )
            .mappings()
            .first()
        )
        latest_status = conn.execute(
            text("""
            SELECT status FROM landing.ingestion_runs
            WHERE pipeline_name='orders_incremental' ORDER BY started_at DESC LIMIT 1
        """)
        ).scalar_one_or_none()
        quality = conn.execute(
            text("""
            SELECT passed FROM control.quality_runs ORDER BY checked_at DESC LIMIT 1
        """)
        ).scalar_one_or_none()
        counts = {}
        for name, query in {
            "raw_orders": "SELECT COUNT(*) FROM landing.raw_order_versions",
            "raw_payments": "SELECT COUNT(*) FROM landing.raw_payment_versions",
            "clickstream": "SELECT COUNT(*) FROM landing.clickstream_events",
            "failed_runs": "SELECT COUNT(*) FROM landing.ingestion_runs WHERE status='failed'",
            "running_runs": "SELECT COUNT(*) FROM landing.ingestion_runs WHERE status='running'",
            "stale_runs": """SELECT COUNT(*) FROM landing.ingestion_runs
                WHERE status='running' AND started_at < NOW()-INTERVAL '1 hour'""",
        }.items():
            counts[name] = int(conn.execute(text(query)).scalar_one())
    age = None if last is None else max(0, (now - last["completed_at"]).total_seconds())
    reasons = []
    if age is None:
        reasons.append("missing_ingestion_success")
    elif age > max_age_seconds:
        reasons.append("ingestion_stale")
    if latest_status == "failed":
        reasons.append("latest_ingestion_failed")
    if quality is not True:
        reasons.append("missing_or_failed_quality")
    if counts["stale_runs"]:
        reasons.append("stale_running_task")
    return {
        "healthy": not reasons,
        "reasons": reasons,
        "last_success_age_seconds": age,
        "quality_passed": quality is True,
        "latest_ingestion_failed": latest_status == "failed",
        **counts,
    }


def prometheus_metrics(health: dict) -> str:
    values = {
        "nusa_pipeline_healthy": int(health["healthy"]),
        "nusa_ingestion_last_success_age_seconds": health["last_success_age_seconds"]
        if health["last_success_age_seconds"] is not None
        else -1,
        "nusa_ingestion_latest_failed": int(health["latest_ingestion_failed"]),
        "nusa_quality_last_run_passed": int(health["quality_passed"]),
        "nusa_raw_orders_total": health["raw_orders"],
        "nusa_raw_payments_total": health["raw_payments"],
        "nusa_clickstream_events_total": health["clickstream"],
        "nusa_ingestion_failed_runs": health["failed_runs"],
        "nusa_ingestion_running_runs": health["running_runs"],
        "nusa_ingestion_stale_runs": health["stale_runs"],
    }
    return "".join(
        f"# TYPE {name} gauge\n{name} {value}\n" for name, value in values.items()
    )


def serve_metrics(
    engine, *, host: str = "127.0.0.1", port: int = 8014, max_age_seconds: int = 86400
) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ("/health", "/metrics"):
                self.send_error(404)
                return
            try:
                health = collect_health(engine, max_age_seconds=max_age_seconds)
                if self.path == "/health":
                    body = json.dumps(health).encode()
                    status = 200 if health["healthy"] else 503
                    content_type = "application/json"
                else:
                    body = prometheus_metrics(health).encode()
                    status, content_type = 200, "text/plain; version=0.0.4"
            except Exception as exc:
                logger.error("monitor_collection_failed code=%s", type(exc).__name__)
                body, status, content_type = (
                    b'{"healthy":false,"reasons":["collection_failed"]}',
                    503,
                    "application/json",
                )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            # Avoid including untrusted request paths or headers in logs.
            return

    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()
