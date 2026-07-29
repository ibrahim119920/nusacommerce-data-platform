import logging
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal

from nusacommerce.domain.order_event import (
    MissingRequiredFieldsError,
    OrderEvent,
    OrderEventParseError,
    OrderEventType,
    OrderEventValidationError,
)


def valid_payload() -> dict:
    return {
        "event_id": "evt-1",
        "order_id": "ord-1",
        "customer_id": "cust-1",
        "event_type": "ORDER_CREATED",
        "event_time": "2026-07-28T12:00:00+07:00",
        "amount": "125000.50",
        "currency": "IDR",
        "version": 1,
    }


class OrderEventTests(unittest.TestCase):
    def test_parse_validate_and_convert_to_record(self) -> None:
        payload = valid_payload() | {"source": "checkout", "metadata": {"attempt": 1}}

        event = OrderEvent.from_dict(payload)
        event.validate()
        record = event.to_record()

        self.assertIs(event.event_type, OrderEventType.ORDER_CREATED)
        self.assertEqual(event.amount, Decimal("125000.50"))
        self.assertIsNotNone(event.event_time.utcoffset())
        self.assertEqual(
            dict(event.extra_fields), {"source": "checkout", "metadata": {"attempt": 1}}
        )
        self.assertEqual(record["amount"], "125000.50")
        self.assertEqual(record["event_time"], "2026-07-28T12:00:00+07:00")
        self.assertEqual(record["extra_fields"]["source"], "checkout")
        self.assertEqual(OrderEvent.from_dict(record).extra_fields, event.extra_fields)

    def test_missing_fields_are_reported_clearly(self) -> None:
        payload = valid_payload()
        del payload["event_id"]
        del payload["amount"]

        with self.assertRaises(MissingRequiredFieldsError) as context:
            OrderEvent.from_dict(payload)

        self.assertEqual(context.exception.fields, ("event_id", "amount"))
        self.assertEqual(str(context.exception), "Missing required field(s): event_id, amount")

    def test_validation_rules(self) -> None:
        invalid_values = (
            ("event_time", "2026-07-28T12:00:00"),
            ("currency", "idr"),
            ("currency", "USDD"),
            ("version", 0),
            ("version", True),
        )
        for field_name, bad_value in invalid_values:
            with self.subTest(field_name=field_name, bad_value=bad_value):
                event = OrderEvent.from_dict(valid_payload() | {field_name: bad_value})
                with self.assertRaises(OrderEventValidationError) as context:
                    event.validate()
                self.assertIn(field_name, context.exception.errors)

    def test_invalid_enum_and_amount_have_safe_parse_errors(self) -> None:
        for field_name, value in (("event_type", "SHIPPED"), ("amount", "not-money")):
            with self.subTest(field_name=field_name):
                with self.assertRaises(OrderEventParseError) as context:
                    OrderEvent.from_dict(valid_payload() | {field_name: value})
                self.assertEqual(context.exception.field_name, field_name)
                self.assertNotIn("cust-1", str(context.exception))

    def test_event_and_nested_extras_are_immutable(self) -> None:
        event = OrderEvent.from_dict(valid_payload() | {"metadata": {"attempt": 1}})

        with self.assertRaises(FrozenInstanceError):
            event.currency = "USD"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            event.extra_fields["new"] = "value"  # type: ignore[index]
        with self.assertRaises(TypeError):
            event.extra_fields["metadata"]["attempt"] = 2  # type: ignore[index]

    def test_validation_log_does_not_contain_payload_or_pii(self) -> None:
        secret = "private-customer-name@example.com"
        event = OrderEvent.from_dict(valid_payload() | {"currency": "id", "email": secret})
        contract_logger = logging.getLogger("nusacommerce.domain.order_event")

        with self.assertLogs(contract_logger, level="WARNING") as captured:
            with self.assertRaises(OrderEventValidationError):
                event.validate()

        rendered_log = " ".join(captured.output)
        self.assertNotIn(secret, rendered_log)
        self.assertNotIn("customer_id", rendered_log)
        self.assertNotIn("currency", rendered_log)
        record = captured.records[0]
        self.assertFalse(hasattr(record, "event_id"))
        self.assertFalse(hasattr(record, "order_id"))
        self.assertEqual(record.validation_fields, ("currency",))

    def test_direct_construction_accepts_timezone_aware_datetime(self) -> None:
        event = OrderEvent(
            event_id="evt-1",
            order_id="ord-1",
            customer_id="cust-1",
            event_type=OrderEventType.PAYMENT_COMPLETED,
            event_time=datetime(2026, 7, 28, tzinfo=timezone.utc),
            amount=Decimal("10.00"),
            currency="USD",
            version=2,
        )
        event.validate()


if __name__ == "__main__":
    unittest.main()
