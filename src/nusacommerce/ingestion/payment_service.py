"""Page-level durable writes; restart from page one after failure."""
from dataclasses import dataclass
from .payment_api import PaymentApiError


@dataclass(frozen=True, slots=True)
class PaymentIngestionResult:
    pages_fetched: int
    payments_received: int
    payments_inserted: int


class PaymentIngestionService:
    def __init__(self, client, repository):
        self.client, self.repository = client, repository

    def run(self):
        cursor = None
        seen = set()
        pages = received = inserted = 0
        while True:
            if cursor in seen:
                raise PaymentApiError("repeated_cursor")
            seen.add(cursor)
            page = self.client.fetch_page(cursor)
            inserted += self.repository.insert_page(page.data)
            pages += 1
            received += len(page.data)
            if page.next_cursor is None:
                return PaymentIngestionResult(pages, received, inserted)
            cursor = page.next_cursor
