# 0001. Count clicks asynchronously through Kafka

Status: accepted

## Context
Redirects are the hot path; users wait on them. Updating a counter in Postgres inside the redirect would add a database write to every click and couple redirect availability to the database's write path.

## Decision
The API publishes a click event to Kafka (buffered, non-blocking) and returns the 307 immediately. A separate worker consumes events and updates counts.

## Consequences
- Redirects stay fast and keep working if counting falls behind.
- Stats are eventually consistent, typically about a second behind.
- Events are replayable, so new consumers (fraud checks, geo stats) can be added later without touching the API.
- More moving parts: a broker to run and consumer lag to watch.
