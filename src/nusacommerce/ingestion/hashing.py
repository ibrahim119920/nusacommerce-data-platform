"""Canonical hashing utilities for ingestion records."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def canonical_payload_json(payload: dict[str, Any]) -> str:
    """Serialize a payload deterministically for storage and hashing."""
    return json.dumps(
        payload,
        default=_json_default,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def hash_payload(payload: dict[str, Any]) -> str:
    """Return the lowercase SHA-256 hash of a canonical payload."""
    canonical_payload = canonical_payload_json(payload)
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        # Keep decimal precision exact instead of converting money to float.
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    # Handle scalar values returned by pandas and NumPy (e.g. numpy.int64).
    item = getattr(value, "item", None)
    if callable(item):
        return item()

    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
