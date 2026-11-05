# System design: "Design a URL shortener"

One of the most common system design questions, and one you've actually built. Use this structure, out loud, in about 35 minutes. Keep pointing back to what you measured in LinkPulse.

## 1. Clarify requirements (3-5 min)

Ask, don't assume. Typical answers:

Functional:
- Create a short link for a long URL; redirect short to long.
- Optional: custom aliases, expiry, click analytics, user accounts.

Non-functional:
- Redirects must be fast (tens of ms) and highly available; they're the product.
- Reads vastly outnumber writes (often 100:1).
- Short codes must be unique and ideally not guessable.
- Analytics can be slightly delayed.

## 2. Estimate (3 min)

Example assumptions: 1 million new links a day, 100 million redirects a day.

| Quantity | Estimate |
| --- | --- |
| Writes | 1M / 86,400 s ≈ 12 per second |
| Reads | 100M / 86,400 s ≈ 1,200 per second average; plan for 5x peaks ≈ 6,000/s |
| Storage per link | about 500 bytes |
| 5 years of links | 1M x 365 x 5 ≈ 1.8 billion links ≈ 1 TB |
| Code length | base62, 7 characters = 62^7 ≈ 3.5 trillion codes, plenty |

Conclusion to state: read-heavy, small data per item, so caching is the main lever, and the analytics write volume (one event per redirect) is larger than the link write volume.

## 3. API (2 min)

```
POST /links            {long_url} -> 201 {code, short_url}
GET  /{code}           -> 307 Location: long_url   (or 404)
GET  /links/{code}/stats -> {total, daily[]}
```

Mention: 307/302 rather than 301 if you count clicks, because browsers cache 301s and skip your server.

## 4. Data model (3 min)

```
links(id, code UNIQUE, long_url, created_at, [owner_id, expires_at])
daily_clicks(code, day, count)   PRIMARY KEY (code, day)
```

The unique index on code serves both uniqueness and the lookup.

## 5. Generating codes (5 min)

| Option | Pros | Cons |
| --- | --- | --- |
| Random base62 (LinkPulse) | Unpredictable, no coordination | Rare collisions; retry on unique violation |
| Counter + base62 | No collisions, shortest codes | Predictable/enumerable; needs a distributed counter or ID ranges per server |
| Hash of URL (truncated) | Same URL, same code | Collisions after truncation; can't create two links for one URL |
| Pre-generated key pool | Fast, no collisions at write time | Extra service to manage |

Say why you chose random: privacy (codes can't be enumerated) and simplicity; the database's unique constraint plus a retry handles collisions without a check-then-insert race.

## 6. The read path (5 min)

```
Client -> CDN/edge (optional) -> load balancer -> stateless API x N -> Redis -> DB
```

- Cache-aside in Redis; hot links follow a power law, so a modest cache serves most traffic. LinkPulse measured ~25 ms miss vs ~3 ms hit.
- Stateless API replicas behind a load balancer scale horizontally.
- Read replicas for the database if cache misses grow.
- Failure: if the cache dies, fall back to the database (LinkPulse does this with short timeouts).

## 7. Analytics (5 min)

Don't write a counter in the redirect path.

```
API --click event--> Kafka --consumers--> aggregate --> analytics store
```

- Events are keyed by code for per-link ordering; partitions give parallelism.
- At-least-once delivery plus idempotent consumers (dedupe by event ID) gives correct counts. LinkPulse proved this by replaying the topic.
- Aggregate before writing (per batch, per code and day) to cut write volume.
- At scale, use an analytics database (ClickHouse, Druid, BigQuery) or stream processing (Flink) for richer stats.

## Scaling it

What breaks first, and the fix:

| Bottleneck | Fix |
| --- | --- |
| Database reads | Cache hit ratio, read replicas, CDN for hottest links |
| Database size | Shard by hash of code (codes are random, so load spreads evenly) |
| Analytics writes | Batch upserts, more partitions and consumers, move to an OLAP store |
| Single Kafka broker | Kafka cluster with replication factor 3 (or a managed service) |
| Single region | Multi-region read path; links are write-once, so replication is simple |
| Abuse | Rate limits per user/IP, URL safety checks, authentication for creation |

## 8. Wrap up with trade-offs (2 min)

- Eventual consistency for stats in exchange for fast, reliable redirects.
- Random codes trade a rare retry for privacy.
- Caching trades possible staleness (if links are editable) for latency; use TTLs and invalidation.

## LinkPulse vs the textbook answer

| Area | Textbook at scale | LinkPulse | Why |
| --- | --- | --- | --- |
| Compute | Many nodes, autoscaling | 1 k3s node, 2 API replicas | Cost; same concepts |
| Cache | Redis cluster / ElastiCache | Single Redis pod | Cost |
| Events | Kafka cluster, RF 3 | Single broker | Cost; replication explained |
| Database | Sharded / replicas | One RDS instance | Data size is tiny |
| Analytics store | OLAP database | Postgres table | Simple daily counts |
| Deploys | GitOps, multi-region | Pipeline over SSH, one region | Scope |
