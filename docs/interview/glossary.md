# Glossary

One line each. Read the night before.

## Python and APIs
- Generator: function that yields values lazily; used for setup/teardown around a request.
- Decorator: function that wraps another to add behaviour.
- Context manager: object for `with` that guarantees cleanup.
- GIL: CPython lock allowing one thread to run Python bytecode at a time.
- Dependency injection: framework supplies what a function declares it needs.
- Pydantic: validation and parsing from type hints.
- REST: resources + HTTP methods + status codes + stateless requests.
- Idempotent (HTTP): repeating the request has the same effect as doing it once.
- 307 vs 301: temporary (not cached) vs permanent (cached) redirect.
- 422: request well-formed but invalid. 429: too many requests. 503: temporarily unavailable.

## Data
- ACID: atomic, consistent, isolated, durable transactions.
- Index: sorted structure for fast lookups, costs writes and space.
- Unique constraint: database-enforced uniqueness, avoids check-then-insert races.
- Upsert: insert or update in one statement (`ON CONFLICT DO UPDATE`).
- Composite key: primary key made of several columns, e.g. `(code, day)`.
- Migration: versioned, reviewable schema change.
- Expand and contract: zero-downtime schema change in steps.
- Connection pool: reused database connections.
- N+1 problem: one query per item after loading a list.

## Caching
- Cache-aside: read cache, on miss read DB and fill cache.
- Write-through: write cache and DB together.
- TTL: time to live; key expires automatically.
- Cache stampede: many simultaneous misses on one hot key.
- Graceful degradation: lose a helper, get slower, don't break.
- Fixed window / sliding window / token bucket: rate-limiting algorithms.
- Fail open / fail closed: allow or block when the limiter itself fails.

## Messaging
- Topic: named stream of events. Partition: ordered shard of a topic. Offset: position in a partition.
- Key: decides the partition; same key, same order.
- Consumer group: consumers sharing partitions; one partition per consumer.
- Rebalance: partitions reassigned when consumers join or leave.
- Consumer lag: how far behind the newest offset a group is.
- At-least-once: may duplicate, never loses (commit after processing).
- Idempotent consumer: processing the same event twice has no extra effect.
- Dead-letter topic: where unprocessable messages go.
- Poison pill: a message that crashes every consumer that reads it.
- Eventual consistency: data becomes correct shortly, not instantly.
- acks=all: broker confirms only after the event is safely stored.

## Containers and Kubernetes
- Image / container: template / running instance.
- Layer cache: unchanged build steps are reused.
- Multi-stage build: build tools stay out of the final image.
- Pod: smallest unit, one or more containers.
- Deployment: keeps N pods running, manages rollouts.
- Service: stable name and load balancing to ready pods.
- Label / selector: how objects find each other.
- ConfigMap / Secret: configuration / sensitive configuration (base64, not encrypted).
- Liveness probe: fails, container restarted. Readiness probe: fails, removed from traffic.
- Rolling update: replace pods gradually; maxSurge / maxUnavailable control the pace.
- Job: runs to completion (migrations).
- PVC: persistent disk for a pod.
- Ingress: HTTP routing from outside to Services (Traefik in k3s).
- Kustomize: base + per-environment overlays.
- Declarative: desired state in files; the cluster converges to it.
- k3s / kind: lightweight Kubernetes / Kubernetes in Docker.

## CI/CD and cloud
- CI: automatic build and test of every change. CD: automatic release of passing changes.
- Pipeline / stage / job / runner: the run / ordered group / single task / machine that executes it.
- Protected variable: only given to protected branches.
- Immutable tags: one tag, one build (commit SHA).
- Smoke test: quick check that a deployment answers.
- VPC: private network in AWS. Security group: stateful firewall.
- IAM least privilege: only the permissions needed.
- IAM role vs user: temporary vs long-lived credentials.
- OIDC (for CI): CI proves identity to AWS without stored keys.
- Elastic IP: fixed public IP. ECR: image registry. RDS: managed database.
- GitOps: the cluster pulls desired state from git (Argo CD).
- Host key pinning: SSH trusts only a known server identity.
