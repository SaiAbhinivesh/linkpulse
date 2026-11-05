# Learning path

LinkPulse was built in eight milestones, each adding one layer. If you want to learn by building it yourself, follow them in order; each one ends with something that works.

Rough time: two to three focused days.

| Milestone | You build | You learn |
| --- | --- | --- |
| M1 | Shortener API with Postgres | REST, FastAPI, Pydantic, SQLAlchemy, Alembic |
| M2 | Redis cache, rate limit, tests | Caching patterns, decorators, pytest fixtures |
| M3 | Kafka click events, stats worker | Event-driven design, consumer groups, idempotency |
| M4 | Docker Compose for the whole stack | Images, layers, multi-stage builds, container networking |
| M5 | Local Kubernetes with kind | Pods, Deployments, Services, probes, rollouts |
| M6 | GitLab CI: lint and test | Pipelines, stages, service containers, merge gates |
| M7 | AWS by hand: ECR, RDS, EC2 + k3s | IAM, security groups, VPCs, managed databases |
| M8 | Continuous deployment to AWS | Image tagging, protected secrets, automated rollouts |

## M1. Shortener API with Postgres

Build: `POST /links`, `GET /{code}` (307 redirect), `GET /links` (paginated), `GET /health`; tables `links` and `daily_clicks`; the first Alembic migration.

Check yourself:
- Why 307 and not 301 for a shortener that counts clicks?
- Why let the unique index catch code collisions instead of checking first?
- Why use migrations instead of `create_all()`?

## M2. Redis cache, rate limiting, tests

Build: cache-aside redirects with a TTL, a `@timed` decorator, a fixed-window rate limit on `POST /links` (INCR + EXPIRE), a pytest suite with a separate test database and fakeredis, ruff.

Check yourself:
- What goes wrong with the cache if links can be edited? Two ways to fix it.
- Fixed window vs sliding window: what's the weakness of a fixed window?
- Why do tests patch `api.rate_limit.redis_client` and not only `api.cache.redis_client`?

## M3. Kafka click events and the stats worker

Build: a producer that publishes a click event per redirect (keyed by code), a worker in the `stats-workers` consumer group that batches events, dedupes by `event_id`, upserts daily counts, and commits offsets after the database transaction; `GET /links/{code}/stats`.

Try: rewind the consumer group to the earliest offset and replay; the counts must not change. Run two workers and watch partitions rebalance.

Check yourself:
- What happens if the worker crashes after the DB commit but before the offset commit?
- Why key events by code?
- With 3 partitions, what happens if you run 5 workers?

## M4. Docker Compose

Build: a multi-stage Dockerfile (non-root user), `compose.yaml` with healthchecks and ordered startup, one-shot `migrate` and `kafka-init` services, Kafka with separate listeners for containers and the host.

Check yourself:
- Why does `DATABASE_URL` say `postgres:5432` inside Compose but `localhost:5433` on your machine?
- Why copy `requirements.txt` before the source code?

## M5. Kubernetes with kind

Build: namespace, Deployments and Services, a PVC for Postgres, ConfigMap and Secrets, migrations as a Job, liveness (`/health`) vs readiness (`/ready`), a rolling update strategy with `maxUnavailable: 0`.

Try: delete a pod; scale Postgres to 0 and watch API pods leave the Service without restarting; roll out a new tag, ship a broken tag, roll back.

Check yourself:
- Why must `/health` not check the database?
- Why didn't the broken release cause downtime?

## M6. GitLab CI

Build: lint and test stages, Postgres as a CI service, JUnit reports, merge request pipelines, "Pipelines must succeed" and a protected `main`.

Try: push a deliberately failing test and watch the merge get blocked.

## M7. AWS by hand

Build: ECR repository, least-privilege IAM user for CI, private RDS, EC2 (k3s) with an Elastic IP, security group to security group access, kubectl over an SSH tunnel, a Kustomize overlay for AWS, a Traefik Ingress.

Follow: [deploy-to-aws.md](deploy-to-aws.md), steps 1-9.

## M8. Continuous deployment

Build: a `build` job (Docker-in-Docker, push SHA-tagged image to ECR) and a `deploy` job (SSH, refresh the pull secret, run migrations, roll out, smoke test), protected variables, a dedicated deploy key with a pinned host key, real client IPs behind Traefik.

Follow: [deploy-to-aws.md](deploy-to-aws.md), steps 10-11, and [ci-cd.md](ci-cd.md).

## Where to go next

- Port the pipeline to GitHub Actions.
- Add a test for the worker's `save()` (run it twice with the same events).
- Add a dead-letter topic for malformed events.
- Replace the fixed-window rate limiter with a sliding window or token bucket.
- Move the AWS setup into Terraform.
