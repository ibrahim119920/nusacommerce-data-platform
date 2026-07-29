"""Run local examples that demonstrate the OrderEvent contract.

This script is deliberately self-contained: it does not call an API or database.
Run it from the repository with ``python scripts/validate_examples.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


# Allow the script to run from a fresh checkout without installing the package.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nusacommerce.domain.order_event import (  # noqa: E402
    OrderEvent,
    OrderEventValidationError,
)


def valid_payload() -> dict[str, Any]:
    return {
        "event_id": "evt-example-001",
        "order_id": "order-example-001",
        "customer_id": "customer-example-001",
        "event_type": "ORDER_CREATED",
        "event_time": "2026-07-28T10:00:00+07:00",
        "amount": "150000.00",
        "currency": "IDR",
        "version": 1,
        "campaign_id": "campaign-july",
    }


def assert_rejected(payload: dict[str, Any], expected_field: str) -> None:
    event = OrderEvent.from_dict(payload)
    try:
        event.validate()
    except OrderEventValidationError as exc:
        assert expected_field in exc.errors, (
            f"Expected validation error for {expected_field!r}, "
            f"received errors for {tuple(exc.errors)!r}"
        )
    else:
        raise AssertionError(f"Payload with invalid {expected_field!r} was accepted")


def main() -> None:
    # 1. A valid payload can be parsed and validated.
    event = OrderEvent.from_dict(valid_payload())
    event.validate()
    assert event.event_id == "evt-example-001"
    print("PASS: valid payload parsed and validated")

    # 2. An unknown field is isolated in extra_fields.
    assert event.extra_fields["campaign_id"] == "campaign-july"
    assert "campaign_id" not in OrderEvent.REQUIRED_FIELDS
    print("PASS: campaign_id stored in extra_fields")

    # 3. Datetimes without a UTC offset are rejected.
    assert_rejected(
        valid_payload() | {"event_time": "2026-07-28T10:00:00"},
        "event_time",
    )
    print("PASS: naive datetime rejected")

    # 4. Contract versions start at one.
    assert_rejected(valid_payload() | {"version": 0}, "version")
    print("PASS: version zero rejected")

    # 5. Currency must consist of three uppercase ASCII letters.
    assert_rejected(valid_payload() | {"currency": "idr"}, "currency")
    print("PASS: lowercase currency rejected")

    print("All local OrderEvent examples passed.")


if __name__ == "__main__":
    main()
