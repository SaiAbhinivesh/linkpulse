# 0002. Idempotent consumer instead of exactly-once

Status: accepted

## Context
Kafka consumers get at-least-once delivery: after a crash between processing and committing offsets, messages are redelivered. Counting naively would double-count. Kafka's exactly-once transactions only cover Kafka-to-Kafka flows, not writes to Postgres.

## Decision
Each event carries a UUID `event_id`. In one Postgres transaction the worker inserts the IDs into `processed_events` (`ON CONFLICT DO NOTHING ... RETURNING`), counts only the new ones, and upserts `daily_clicks`. Offsets are committed only after that transaction.

## Consequences
- Replays and redeliveries are harmless; verified by rewinding the consumer group.
- `processed_events` grows forever. Production would prune rows older than the topic's retention period.
- One extra insert per event.
