import json
import logging
import uuid
from datetime import UTC, datetime

from confluent_kafka import KafkaException, Producer

from api.config import settings

logger = logging.getLogger("linkpulse")

_producer: Producer | None = None


def get_producer() -> Producer:
    global _producer
    if _producer is None:
        _producer = Producer(
            {
                "bootstrap.servers": settings.kafka_bootstrap_servers,
                "client.id": "linkpulse-api",
                "acks": "all",
                "enable.idempotence": True,
                "linger.ms": 5,
            }
        )
    return _producer


def _on_delivery(err, msg) -> None:
    if err is not None:
        logger.warning("Click event delivery failed: %s", err)


def publish_click(code: str, user_agent: str | None) -> None:
    event = {
        "event_id": str(uuid.uuid4()),
        "code": code,
        "ts": datetime.now(UTC).isoformat(),
        "user_agent": user_agent,
    }
    try:
        producer = get_producer()
        producer.produce(
            settings.clicks_topic,
            key=code,
            value=json.dumps(event),
            on_delivery=_on_delivery,
        )
        producer.poll(0)
    except (BufferError, KafkaException) as exc:
        logger.warning("Could not publish click event: %s", exc)


def flush_producer(timeout: float = 5.0) -> None:
    if _producer is not None:
        _producer.flush(timeout)
