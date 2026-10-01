"""Small models shared by the incremental-ingestion workflow."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ExtractionWindow:
    """A fixed, half-open interval: start <= updated_at < end."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        for value in (self.start, self.end):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Extraction timestamps must include a timezone")
        if self.start > self.end:
            raise ValueError("Window start must not be after window end")
