# 0003. Cache-aside with graceful degradation

Status: accepted

## Context
Redirects vastly outnumber link creations, and links rarely change. Postgres lookups are about 25 ms; Redis hits about 3 ms.

## Decision
Cache-aside: read Redis first, fall back to Postgres on a miss, then store with a 1-hour TTL. Every Redis call has a 0.5 s timeout and treats errors as misses. The rate limiter also fails open.

## Consequences
- Redis is an optimization, never a dependency; an outage makes redirects slower, not broken.
- Stale data is possible for up to the TTL if links become editable (would need invalidation on update).
- During a Redis outage each request can wait up to the timeout; a circuit breaker would fix that.
- `/ready` deliberately ignores Redis.
