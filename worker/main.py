import json
import logging
import signal
from collections import Counter
from datetime import datetime

from confluent_kafka import Consumer, KafkaError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from api.config import settings
from api.db import SessionLocal
from api.models import DailyClick, ProcessedEvent

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("linkpulse.worker")

BATCH_SIZE = 100
POLL_TIMEOUT_SECONDS = 1.0

running = True


def stop(signum, frame) -> None:
    global running
    logger.info("Shutting down after the current batch...")
    running = False


def parse(messages) -> list[dict]:
    events = []
    for msg in messages:
        if msg.error():
            if msg.error().code() != KafkaError._PARTITION_EOF:
                logger.warning("Kafka error: %s", msg.error())
            continue
        try:
            event = json.loads(msg.value())
            events.append(
                {
                    "event_id": event["event_id"],
                    "code": event["code"],
                    "day": datetime.fromisoformat(event["ts"]).date(),
                }
            )
        except (ValueError, KeyError) as exc:
            logger.warning("Skipping bad event at offset %s: %s", msg.offset(), exc)
    return events


def save(events: list[dict]) -> int:
    unique = list({e["event_id"]: e for e in events}.values())

    with SessionLocal() as db, db.begin():
        new_ids = set(
            db.scalars(
                pg_insert(ProcessedEvent)
                .values([{"event_id": e["event_id"]} for e in unique])
                .on_conflict_do_nothing(index_elements=["event_id"])
                .returning(ProcessedEvent.event_id)
            )
        )

        counts = Counter((e["code"], e["day"]) for e in unique if e["event_id"] in new_ids)
        if counts:
            stmt = pg_insert(DailyClick).values(
                [{"code": code, "day": day, "count": n} for (code, day), n in counts.items()]
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["code", "day"],
                set_={"count": DailyClick.count + stmt.excluded.count},
            )
            db.execute(stmt)

    return len(new_ids)


def main() -> None:
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": "stats-workers",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([settings.clicks_topic])
    logger.info("Worker started, consuming topic %s", settings.clicks_topic)

    try:
        while running:
            messages = consumer.consume(num_messages=BATCH_SIZE, timeout=POLL_TIMEOUT_SECONDS)
            if not messages:
                continue
            events = parse(messages)
            if events:
                counted = save(events)
                logger.info("Batch of %d messages, %d new clicks counted", len(messages), counted)
            consumer.commit(asynchronous=False)
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
