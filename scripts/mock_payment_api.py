"""Small local Payment API for the Day 3 ingestion exercise."""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


ORDERS = [
    ("ord-1001", "125000.00"),
    ("ord-1002", "250000.00"),
    ("ord-1003", "89000.00"),
    ("ord-1005", "310000.00"),
    ("ord-1007", "499000.00"),
    ("ord-1008", "72000.00"),
]

PAYMENTS = [
    {
        "payment_id": f"pay-{number}",
        "order_id": order_id,
        "version": 1,
        "amount": amount,
        "currency": "IDR",
        "status": "succeeded",
        "updated_at": "2026-09-28T10:20:00+07:00",
    }
    for number, (order_id, amount) in enumerate(ORDERS, start=1)
]


class PaymentHandler(BaseHTTPRequestHandler):
    """Serve two payments per page and one temporary 429 response."""

    rate_limit_sent = False
    page_size = 2

    def _send_json(
        self,
        status_code: int,
        payload: dict,
        *,
        retry_after: int | None = None,
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if retry_after is not None:
            self.send_header("Retry-After", str(retry_after))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        if parsed_url.path != "/payments":
            self._send_json(404, {"error": "not_found"})
            return

        cursor_token = parse_qs(parsed_url.query).get("cursor", ["0"])[0]
        try:
            offset = int(cursor_token)
            if not 0 <= offset <= len(PAYMENTS):
                raise ValueError
        except ValueError:
            self._send_json(400, {"error": "invalid_cursor"})
            return

        if offset == self.page_size and not PaymentHandler.rate_limit_sent:
            PaymentHandler.rate_limit_sent = True
            self._send_json(429, {"error": "rate_limited"}, retry_after=1)
            return

        page_end = offset + self.page_size
        next_cursor = str(page_end) if page_end < len(PAYMENTS) else None
        self._send_json(
            200,
            {"data": PAYMENTS[offset:page_end], "next_cursor": next_cursor},
        )


if __name__ == "__main__":
    print("Payment API running at http://127.0.0.1:8000")
    HTTPServer((os.getenv("PAYMENT_BIND_HOST", "127.0.0.1"),
                int(os.getenv("PAYMENT_PORT", "8000"))), PaymentHandler).serve_forever()
