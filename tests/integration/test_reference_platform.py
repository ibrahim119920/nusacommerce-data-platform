"""Day 6/8 correctness on a disposable *_test database."""
import os
import unittest
from datetime import datetime
from unittest.mock import Mock
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from nusacommerce.platform import bootstrap
from nusacommerce.ingestion.repository import OrderIngestionRepository
from nusacommerce.ingestion.service import IncrementalOrderIngestion
from nusacommerce.ingestion.payment_repository import PaymentRepository
from nusacommerce.streaming.clickstream import store_event

URL = os.getenv("TEST_POSTGRES_URL")


@unittest.skipUnless(URL,"TEST_POSTGRES_URL is required")
class ReferencePlatformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not make_url(URL).database.endswith("_test"):
            raise ValueError("Dedicated test database required")
        cls.engine = create_engine(URL)
        bootstrap(cls.engine)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        with self.engine.begin() as conn:
            conn.execute(text("""TRUNCATE quality.order_conflicts,control.ingestion_checkpoints,
                landing.raw_order_versions,landing.staged_orders,landing.ingestion_runs,
                source.orders,landing.raw_payment_versions,landing.clickstream_events"""))
        bootstrap(self.engine)
        self.repo = OrderIngestionRepository(self.engine)
        self.service = IncrementalOrderIngestion(self.repo,page_size=2)
        self.cutoff = datetime.fromisoformat("2026-09-28T10:20:00+07:00")

    def test_order_conflict_blocks_checkpoint_and_keeps_metadata(self):
        self.service.run(self.cutoff)
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE source.orders SET amount=amount+1 WHERE order_id='ord-1008'"))
        with self.assertRaises(ValueError):
            self.service.run(self.cutoff)
        self.assertEqual(self.repo.load_checkpoint("orders_incremental"),self.cutoff)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT COUNT(*) FROM quality.order_conflicts")).scalar_one(),1)
            self.assertEqual(conn.execute(text("SELECT COUNT(*) FROM landing.raw_order_versions")).scalar_one(),8)

    def test_backfill_does_not_move_regular_checkpoint(self):
        self.service.run(self.cutoff)
        result = self.service.backfill(
            datetime.fromisoformat("2026-09-27T00:00:00+07:00"),
            datetime.fromisoformat("2026-09-28T00:00:00+07:00"))
        self.assertEqual(result["inserted"],0)
        self.assertFalse(result["checkpoint_advanced"])
        self.assertEqual(self.repo.load_checkpoint("orders_incremental"),self.cutoff)

    def test_second_runner_cannot_take_lock(self):
        with self.repo.pipeline_lock("orders_incremental"):
            with self.assertRaises(RuntimeError):
                with self.repo.pipeline_lock("orders_incremental"):
                    self.fail("Second lock was incorrectly acquired")

    def test_empty_window_advances_checkpoint(self):
        self.service.run(self.cutoff)
        later = datetime.fromisoformat("2026-09-29T00:00:00+07:00")
        self.service.run(later)
        final = datetime.fromisoformat("2026-09-30T00:00:00+07:00")
        result = self.service.run(final)
        self.assertEqual(result["extracted"],0)
        self.assertEqual(self.repo.load_checkpoint("orders_incremental"),final)

    def test_payment_rerun_and_conflict(self):
        repo = PaymentRepository(self.engine)
        payment = {"payment_id":"p","order_id":"ord-1001","version":1,"amount":"125000.00",
                   "currency":"IDR","status":"succeeded","updated_at":"2026-09-28T10:00:00+07:00"}
        self.assertEqual(repo.insert_page([payment]),1)
        self.assertEqual(repo.insert_page([payment]),0)
        with self.assertRaises(ValueError):
            repo.insert_page([dict(payment,amount="1.00")])

    def test_invalid_payment_rolls_back_whole_page(self):
        repo = PaymentRepository(self.engine)
        payment = {"payment_id":"p","order_id":"ord-1001","version":1,"amount":"1.00",
                   "currency":"IDR","status":"succeeded","updated_at":"2026-09-28T10:00:00+07:00"}
        with self.assertRaises(ValueError):
            repo.insert_page([payment,dict(payment,payment_id="p2",version=True)])
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT COUNT(*) FROM landing.raw_payment_versions")).scalar_one(),0)

    def test_clickstream_replay_and_payload_conflict(self):
        message = Mock()
        message.topic.return_value="fixture"
        message.partition.return_value=0
        message.offset.return_value=1
        event={"event_id":"e","customer_id":"c","event_type":"page_view",
               "event_time":"2026-10-01T00:00:00+00:00"}
        self.assertEqual(store_event(self.engine,event,message),1)
        self.assertEqual(store_event(self.engine,event,message),0)
        with self.assertRaises(ValueError):
            store_event(self.engine,dict(event,event_type="checkout"),message)
