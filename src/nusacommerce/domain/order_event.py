"""Data contract for order events entering the NusaCommerce platform."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from types import MappingProxyType
from typing import Any, ClassVar, Mapping


logger = logging.getLogger(__name__)


class OrderEventError(ValueError):
    """Base class for errors raised by the order-event contract."""


class MissingRequiredFieldsError(OrderEventError):
    """Raised when a payload omits one or more required fields."""

    def __init__(self, fields: list[str]) -> None:
        self.fields = tuple(fields)
        super().__init__(f"Missing required field(s): {', '.join(fields)}")


class OrderEventParseError(OrderEventError):
    """Raised when a field cannot be converted to its contract type."""

    def __init__(self, field_name: str, expected: str) -> None:
        self.field_name = field_name
        super().__init__(f"Invalid field '{field_name}': expected {expected}")


class OrderEventValidationError(OrderEventError):
    """Raised when a parsed event violates the contract."""

    def __init__(self, errors: Mapping[str, str]) -> None:
        self.errors = MappingProxyType(dict(errors))
        details = "; ".join(f"{name}: {message}" for name, message in errors.items())
        super().__init__(f"OrderEvent validation failed: {details}")


class OrderEventType(str, Enum):
    ORDER_CREATED = "ORDER_CREATED"
    PAYMENT_COMPLETED = "PAYMENT_COMPLETED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    REFUND_ISSUED = "REFUND_ISSUED"


def _freeze(value: Any) -> Any:
    """Make values held by an immutable event resistant to nested mutation."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    """Return ordinary containers suitable for serialization."""
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class OrderEvent:
    event_id: str
    order_id: str
    customer_id: str
    event_type: OrderEventType
    event_time: datetime
    amount: Decimal
    currency: str
    version: int
    extra_fields: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    REQUIRED_FIELDS: ClassVar[tuple[str, ...]] = (
        "event_id",
        "order_id",
        "customer_id",
        "event_type",
        "event_time",
        "amount",
        "currency",
        "version",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "extra_fields", _freeze(dict(self.extra_fields)))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> OrderEvent:
        """Parse a payload without retaining it on parsing or validation errors."""
        if not isinstance(payload, Mapping):
            raise OrderEventParseError("payload", "a mapping")

        missing = [name for name in cls.REQUIRED_FIELDS if name not in payload]
        if missing:
            raise MissingRequiredFieldsError(missing)

        try:
            event_type = OrderEventType(payload["event_type"])
        except (TypeError, ValueError) as exc:
            raise OrderEventParseError(
                "event_type", "one of: " + ", ".join(item.value for item in OrderEventType)
            ) from exc

        event_time = cls._parse_event_time(payload["event_time"])
        amount = cls._parse_amount(payload["amount"])
        version = payload["version"]

        supplied_extras = payload.get("extra_fields", {})
        if not isinstance(supplied_extras, Mapping):
            raise OrderEventParseError("extra_fields", "a mapping")
        known_fields = set(cls.REQUIRED_FIELDS) | {"extra_fields"}
        extras = dict(supplied_extras)
        extras.update({key: value for key, value in payload.items() if key not in known_fields})

        return cls(
            event_id=payload["event_id"],
            order_id=payload["order_id"],
            customer_id=payload["customer_id"],
            event_type=event_type,
            event_time=event_time,
            amount=amount,
            currency=payload["currency"],
            version=version,
            extra_fields=extras,
        )

    @staticmethod
    def _parse_event_time(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise OrderEventParseError("event_time", "an ISO-8601 datetime") from exc
        raise OrderEventParseError("event_time", "a datetime or ISO-8601 string")

    @staticmethod
    def _parse_amount(value: Any) -> Decimal:
        if isinstance(value, bool):
            raise OrderEventParseError("amount", "a decimal number")
        try:
            return value if isinstance(value, Decimal) else Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise OrderEventParseError("amount", "a decimal number") from exc

    def validate(self) -> None:
        """Validate this event, logging metadata only (never the full payload)."""
        errors: dict[str, str] = {}

        for name in ("event_id", "order_id", "customer_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                errors[name] = "must be a non-empty string"

        if not isinstance(self.event_type, OrderEventType):
            errors["event_type"] = "must be a supported OrderEventType"
        if not isinstance(self.event_time, datetime):
            errors["event_time"] = "must be a datetime"
        elif self.event_time.tzinfo is None or self.event_time.utcoffset() is None:
            errors["event_time"] = "must include a timezone"
        if not isinstance(self.amount, Decimal) or not self.amount.is_finite():
            errors["amount"] = "must be a finite Decimal"
        if (
            not isinstance(self.currency, str)
            or len(self.currency) != 3
            or not self.currency.isalpha()
            or not self.currency.isascii()
            or not self.currency.isupper()
        ):
            errors["currency"] = "must be exactly 3 uppercase ASCII letters"
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            errors["version"] = "must be an integer greater than or equal to 1"

        if errors:
            # Values and extra_fields are deliberately excluded to avoid leaking PII.
            logger.warning(
                "OrderEvent validation failed",
                extra={"validation_fields": tuple(errors)},
            )
            raise OrderEventValidationError(errors)

    def to_record(self) -> dict[str, Any]:
        """Produce a serialization-friendly record with extras kept isolated."""
        return {
            "event_id": self.event_id,
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "event_type": self.event_type.value,
            "event_time": self.event_time.isoformat(),
            "amount": str(self.amount),
            "currency": self.currency,
            "version": self.version,
            "extra_fields": _thaw(self.extra_fields),
        }