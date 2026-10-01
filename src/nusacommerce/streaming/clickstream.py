"""At-least-once Kafka delivery with idempotent PostgreSQL writes."""
import json
from datetime import datetime
from pathlib import Path
from time import monotonic
from sqlalchemy import text
from confluent_kafka import Consumer, Producer, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic
from nusacommerce.ingestion.hashing import canonical_payload_json, hash_payload

TOPIC = "nusacommerce.clickstream"


def ensure_topic(bootstrap):
    admin = AdminClient({"bootstrap.servers": bootstrap})
    if TOPIC not in admin.list_topics(timeout=10).topics:
        for future in admin.create_topics([NewTopic(TOPIC, 3, 1)]).values():
            future.result(20)


def produce_fixture(bootstrap, path: Path):
    ensure_topic(bootstrap)
    producer = Producer({"bootstrap.servers": bootstrap, "enable.idempotence": True})
    errors = []
    events = json.loads(path.read_text(encoding="utf-8"))
    def delivered(error, message):
        if error:
            errors.append(str(error))
    for event in events:
        producer.produce(TOPIC, key=event["customer_id"],
                         value=canonical_payload_json(event), on_delivery=delivered)
        producer.poll(0)
    if producer.flush(20) or errors:
        raise RuntimeError("kafka_delivery_failed")
    return len(events)


def store_event(engine, event, message):
    try:
        if not isinstance(event, dict):
            raise ValueError()
        for field in ("event_id", "customer_id", "event_type"):
            if not isinstance(event[field], str) or not event[field]:
                raise ValueError()
        if event["event_type"] not in ("page_view", "add_to_cart", "checkout"):
            raise ValueError()
        if datetime.fromisoformat(event["event_time"]).utcoffset() is None:
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise ValueError("invalid_clickstream_contract") from None
    params = {"id": event["event_id"], "payload": canonical_payload_json(event),
              "hash": hash_payload(event), "topic": message.topic(),
              "partition": message.partition(), "offset": message.offset()}
    with engine.begin() as conn:
        old = conn.execute(text("SELECT payload_hash FROM landing.clickstream_events WHERE event_id=:id"),
                           params).scalar_one_or_none()
        if old is not None and old != params["hash"]:
            raise ValueError("clickstream_payload_conflict")
        rows = conn.execute(text("""INSERT INTO landing.clickstream_events
            (event_id,payload,payload_hash,topic,kafka_partition,kafka_offset)
            VALUES (:id,CAST(:payload AS JSONB),:hash,:topic,:partition,:offset)
            ON CONFLICT (event_id) DO NOTHING RETURNING event_id"""), params).fetchall()
    return len(rows)


def consume(bootstrap, engine, *, group="nusa-reference", max_messages=6, idle_seconds=10):
    consumer = Consumer({"bootstrap.servers": bootstrap, "group.id": group,
                         "auto.offset.reset": "earliest", "enable.auto.commit": False})
    consumer.subscribe([TOPIC])
    received = inserted = 0
    deadline = monotonic() + idle_seconds
    try:
        while received < max_messages and monotonic() < deadline:
            message = consumer.poll(1)
            if message is None:
                continue
            if message.error():
                raise KafkaException(message.error())
            try:
                event = json.loads(message.value())
            except (ValueError, UnicodeDecodeError):
                raise ValueError("invalid_clickstream_json") from None
            inserted += store_event(engine, event, message)
            # PostgreSQL commit has completed; a crash before this commit causes safe replay.
            consumer.commit(message=message, asynchronous=False)
            received += 1
            deadline = monotonic() + idle_seconds
    finally:
        consumer.close()
    return {"received": received, "inserted": inserted, "duplicates": received-inserted}
