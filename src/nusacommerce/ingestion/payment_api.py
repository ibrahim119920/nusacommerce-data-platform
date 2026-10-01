"""Bounded HTTP retries for an immutable cursor-paginated payment feed."""
from dataclasses import dataclass
from time import sleep
from typing import Any
import logging
import requests
logger = logging.getLogger(__name__)


class PaymentApiError(RuntimeError):
    """Safe error: no response body or credentials."""


@dataclass(frozen=True)
class PaymentPage:
    data: list[dict[str, Any]]
    next_cursor: str | None


class PaymentApiClient:
    def __init__(self, base_url, *, session=None, max_attempts=3,
                 timeout=(3, 10), sleeper=sleep):
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.max_attempts, self.timeout, self.sleeper = max_attempts, timeout, sleeper

    def fetch_page(self, cursor=None):
        for attempt in range(1, self.max_attempts + 1):
            delay = min(2 ** (attempt - 1), 30)
            try:
                response = self.session.get(self.base_url + "/payments",
                    params={"cursor": cursor}, timeout=self.timeout)
            except (requests.Timeout, requests.ConnectionError):
                code = "network"
            else:
                code = str(response.status_code)
                if response.status_code == 200:
                    try:
                        body = response.json()
                    except ValueError:
                        raise PaymentApiError("invalid_json") from None
                    if (not isinstance(body, dict) or not isinstance(body.get("data"), list)
                        or "next_cursor" not in body
                        or not all(isinstance(row, dict) for row in body["data"])
                        or not isinstance(body["next_cursor"], (str, type(None)))):
                        raise PaymentApiError("invalid_response_shape")
                    return PaymentPage(body["data"], body["next_cursor"])
                if response.status_code not in (429, 500, 502, 503, 504):
                    raise PaymentApiError("http_" + code)
                if response.status_code == 429:
                    header = response.headers.get("Retry-After", "")
                    if header.isdecimal():
                        delay = min(int(header), 60)
            if attempt == self.max_attempts:
                raise PaymentApiError("attempts_exhausted_" + code)
            logger.warning("payment_request_retry attempt=%s code=%s", attempt, code)
            self.sleeper(delay)
        raise AssertionError("unreachable")

    def close(self):
        self.session.close()
