# Question bank

Cover the answer, say yours out loud, then check. Each answer ends with how LinkPulse shows it, which is what turns a textbook answer into experience.

Topics: [Python](#python) · [FastAPI and REST](#fastapi-and-rest) · [Databases](#databases) · [Caching and Redis](#caching-and-redis) · [Kafka and event-driven design](#kafka-and-event-driven-design) · [Testing](#testing) · [Docker](#docker) · [Kubernetes](#kubernetes) · [CI/CD](#cicd) · [AWS and security](#aws-and-security) · [Reliability and operations](#reliability-and-operations) · [About the project](#about-the-project)

## Python

Q: What is a generator, and where did you use one?
A: A function that yields values one at a time and pauses in between, instead of building everything in memory. Useful for large data and for setup/cleanup around a block. In LinkPulse, `get_db` yields a session to each request and closes it in `finally` afterwards.

Q: What is a decorator? What does `functools.wraps` do?
A: A function that takes a function and returns a new one wrapping extra behaviour around it. `wraps` copies the original name, docstring and signature onto the wrapper. In LinkPulse, `@timed` logs latency; without `wraps`, FastAPI couldn't see the endpoint's parameters and dependency injection would break.

Q: What is a context manager?
A: An object used with `with` that runs setup on entry and cleanup on exit, even if an exception occurs. The worker uses `with SessionLocal() as db, db.begin():` so the transaction commits on success and rolls back on error.

Q: What's the GIL, and how does it affect a web API?
A: CPython's Global Interpreter Lock lets only one thread run Python bytecode at a time. I/O-bound work (waiting on databases, networks) still benefits from threads or async because the GIL is released while waiting; CPU-bound work needs multiple processes. An API like LinkPulse is I/O-bound, and scales out with more replicas.

Q: def vs async def in FastAPI?
A: async def runs on the event loop and must only call non-blocking code. Plain def runs in a thread pool, so blocking libraries are safe there. LinkPulse uses synchronous SQLAlchemy, so its endpoints are plain def. Calling blocking code inside async def would stall every request on that worker.

Q: Why a virtual environment and requirements files?
A: Isolation and reproducibility: each project gets its own package versions, and the same set can be installed on any machine, CI or Docker. LinkPulse splits runtime (`requirements.txt`, goes into the image) from dev tools (`requirements-dev.txt`).

Q: Mutable default arguments: what's the bug?
A: Defaults are evaluated once when the function is defined, so a default list or dict is shared between calls. Use None and create inside. Ruff's bugbear rule B008 flags calls in defaults; LinkPulse whitelists FastAPI's `Depends`/`Query`, which are markers, not shared state.

## FastAPI and REST

Q: What makes an API RESTful?
A: Resources identified by URLs, HTTP methods expressing the action, stateless requests, and standard status codes. LinkPulse: `POST /links`, `GET /links`, `GET /links/{code}/stats`, `GET /{code}`.

Q: Which status codes did you use and why?
A: 201 for created links, 307 for redirects, 404 for unknown codes, 422 for invalid input (FastAPI's validation), 429 with Retry-After for rate limiting, 503 from /ready when the database is down.

Q: 301 vs 302 vs 307 vs 308?
A: 301/308 permanent and cacheable; 302/307 temporary. 307/308 guarantee the method is kept. LinkPulse uses 307 so browsers don't cache the redirect and every click reaches the server to be counted.

Q: Idempotency of HTTP methods?
A: GET, PUT, DELETE are idempotent: repeating them has the same effect. POST is not: two POST /links calls make two links.

Q: Offset vs cursor pagination?
A: Offset is simple and allows jumping to a page, but gets slow deep into a big table and can shift as rows are added. Cursor ("items after id X") stays fast and stable. LinkPulse uses limit/offset, capped at 100 per page, with a stable sort.

Q: What does Pydantic give you?
A: Validation and parsing from type hints, clear 422 errors, and response models that control exactly what is returned. `HttpUrl` rejects invalid URLs before my code runs.

Q: How does dependency injection work in FastAPI, and why is it useful?
A: Parameters declared with `Depends()` are provided per request by FastAPI. It keeps endpoints simple and makes testing easy: LinkPulse's tests override `get_db` to point at a test database, and the rate limiter is attached as a dependency on one route.

Q: Why must `/{code}` be the last route?
A: FastAPI matches routes in order and `/{code}` matches almost any single-segment path, so it would swallow `/health`, `/ready` or `/links`.

## Databases

Q: What's an index, and its cost?
A: A sorted structure (usually a B-tree) that finds rows without scanning the table. It speeds reads and slows writes and uses space. `links.code` has a unique index, which both enforces uniqueness and makes the redirect lookup fast.

Q: How do you avoid duplicate short codes?
A: Let the database enforce it with a unique constraint, and retry on IntegrityError. Checking first then inserting has a race between concurrent requests.

Q: What's a transaction? Why roll back after an error?
A: A unit of work that succeeds or fails as a whole (ACID). After a failed statement the session is in a failed state; rollback clears it so the next attempt can run.

Q: What is an upsert?
A: Insert, or update if the row exists, in one atomic statement: `INSERT ... ON CONFLICT (...) DO UPDATE`. The worker uses it to add to `daily_clicks`; the composite key `(code, day)` defines the conflict.

Q: Why migrations instead of creating tables from code?
A: `create_all` can't change existing tables or move data. Migrations are versioned, reviewable and repeatable in every environment. LinkPulse added `processed_events` as a second migration, without touching existing data.

Q: How would you change a schema with zero downtime?
A: Expand and contract: add new columns nullable, deploy code that writes both, backfill, switch reads, then drop the old column in a later release. Needed because old and new pods run together during a rolling update.

Q: N+1 queries?
A: Loading a list, then running one extra query per item. Fix with joins or eager loading.

Q: What is connection pooling?
A: Reusing open database connections instead of opening one per request. The SQLAlchemy engine pools; `pool_pre_ping` checks a connection is alive before use. Watch the total: replicas x pool size must stay under the database's connection limit.

Q: Why a managed database (RDS)?
A: Backups, patching, monitoring and failover are handled for you. In LinkPulse it's the one component I didn't run inside Kubernetes.

## Caching and Redis

Q: Explain cache-aside.
A: Read the cache; on a miss read the database and fill the cache. Only data that's actually used gets cached, and a cache outage just means slower reads. LinkPulse: 25 ms miss vs about 3 ms hit.

Q: Cache-aside vs write-through?
A: Write-through updates the cache on every write, so reads rarely miss but writes are slower and the cache holds unread data.

Q: How do you handle stale data?
A: TTLs bound staleness; invalidate (delete the key) when the source changes. LinkPulse uses a 1-hour TTL; links aren't editable yet, so no invalidation is needed.

Q: What is a cache stampede?
A: Many requests miss on the same hot key at once and all hit the database. Mitigate with locking per key, early refresh, or warming.

Q: What happens in your app when Redis is down?
A: Calls have a 0.5 s timeout and errors count as misses, so redirects go to Postgres. The rate limiter fails open.

Q: How does your rate limiter work? Weaknesses?
A: Fixed window: key per IP per minute, INCR then EXPIRE in one pipeline, 429 above 10. INCR is atomic, so it works across replicas. Weakness: bursts straddling a minute boundary can double the limit. Sliding windows or token buckets fix that.

Q: Fail open or fail closed?
A: Depends on what the limiter protects. For link creation, availability matters more, so open. For login or payment fraud, closed.

## Kafka and event-driven design

Q: Why put Kafka between the redirect and the counting?
A: The redirect stays fast and doesn't depend on the counting path; counting can lag, retry and replay. Other consumers can be added later. Cost: eventual consistency and another system to run.

Q: Topic, partition, offset, consumer group?
A: A topic is a named log; partitions split it for parallelism, each ordered; an offset is a position in a partition; a consumer group shares partitions among its members, and each partition goes to one member. LinkPulse: topic `clicks`, 3 partitions, group `stats-workers`.

Q: Why key events by short code?
A: The same key always goes to the same partition, so a link's clicks stay in order and are processed by one worker at a time.

Q: At-most-once, at-least-once, exactly-once?
A: At-most-once may lose messages (commit before processing); at-least-once may duplicate (commit after processing); exactly-once needs idempotent or transactional processing. LinkPulse is at-least-once plus idempotent processing.

Q: How did you make the consumer idempotent?
A: Event UUID recorded in `processed_events` in the same transaction as the count update; only new IDs are counted; offsets committed after the commit. Tested by replaying the whole topic: 0 double counts.

Q: Your worker crashes after writing to the DB but before committing offsets. What happens?
A: Kafka redelivers the batch; the IDs are already in `processed_events`, so nothing is counted again.

Q: How do you scale consumers? What's the limit?
A: Add consumers to the group; Kafka rebalances. More consumers than partitions leaves some idle, so partitions set the ceiling (3 here).

Q: What is consumer lag?
A: How far a group is behind the newest offset. Growing lag means consumers can't keep up; it's the key consumer metric.

Q: How do you handle a malformed message?
A: Don't let it block the partition (a poison pill). LinkPulse logs and skips it; production would send it to a dead-letter topic for inspection.

Q: Kafka vs a traditional queue (RabbitMQ, SQS)?
A: Kafka is a durable, replayable log with ordered partitions and many independent consumer groups; queues usually delete messages once consumed and focus on per-message routing and acknowledgements.

Q: Producer settings you chose?
A: acks=all (stored safely before confirmation), idempotence on (no duplicates from retries), linger.ms=5 (small batches). produce() is non-blocking; a background thread sends.

## Testing

Q: Unit vs integration tests?
A: Unit tests check logic in isolation (code generation); integration tests check pieces together (API + validation + SQLAlchemy + real Postgres). LinkPulse has both.

Q: How did you test code that uses Redis and Kafka?
A: fakeredis replaces the Redis client; the Kafka publish function is replaced with one that records calls. The database is real (a separate test database) because SQL behaviour matters.

Q: Why does each test start with an empty database?
A: Isolation: results don't depend on test order or leftovers.

Q: What's a flaky test you know about?
A: The rate-limit test can fail if its 11 requests straddle a minute boundary. Fix by freezing or injecting the clock.

Q: Why "patch where it's used"?
A: `from x import y` copies the name into the importing module, so patching `x.y` doesn't affect it. LinkPulse patches `api.rate_limit.redis_client` and `api.main.publish_click`.

## Docker

Q: Image vs container?
A: An image is the read-only template; a container is a running instance of it.

Q: Why a multi-stage build?
A: Build tools and caches stay in the builder stage; the runtime image contains only the virtualenv and code: smaller, less to attack.

Q: Why copy requirements before code?
A: Layer caching: code changes don't invalidate the slow dependency install.

Q: Why run as a non-root user?
A: Limits damage if the app is compromised.

Q: "localhost" inside a container?
A: The container itself. Containers reach each other by service name (`postgres:5432`), not via localhost.

Q: What's in .dockerignore and why?
A: `.venv`, caches, `.git`, tests and `.env`: smaller build context and no secrets baked into images.

Q: Building on an M-series Mac for an Intel server?
A: Build for `linux/amd64`, or the container fails with "exec format error".

## Kubernetes

Q: Pod vs Deployment vs Service?
A: A pod runs containers; a Deployment keeps N pods running and manages updates; a Service gives a stable name and load-balances to ready pods selected by labels.

Q: Liveness vs readiness?
A: Liveness failing restarts the container; readiness failing removes it from Service traffic. Liveness should not depend on external systems, or an outage causes restart storms. LinkPulse: /health vs /ready.

Q: How does a rolling update work with maxSurge 1, maxUnavailable 0?
A: Start one new pod, wait until it's ready, remove one old pod, repeat. Capacity never drops, and a broken release just stalls.

Q: How do you roll back?
A: `kubectl rollout undo`, or redeploy a previous image tag.

Q: ConfigMap vs Secret? Are Secrets secure?
A: Same mechanism; Secrets are for sensitive values and are only base64-encoded, so security comes from access control and encryption at rest.

Q: Why run migrations as a Job?
A: Once per release, before the new code needs the schema, not once per replica at startup.

Q: Requests vs limits?
A: Requests are reserved for scheduling; limits cap usage. Exceeding a memory limit kills the container.

Q: Why a PVC for Postgres, and why `Recreate`?
A: Data outlives pods; and two Postgres servers must never share a data directory, so stop the old one first.

Q: What is an Ingress?
A: Rules for routing external HTTP traffic to Services, implemented by a controller (Traefik in k3s).

Q: Declarative vs imperative?
A: Declarative: describe desired state in files and apply; imperative: commands like `kubectl scale`. The files in git are the source of truth; the next apply overrides manual changes.

Q: What is Kustomize?
A: A built-in way to keep a base set of manifests and per-environment overlays with only the differences. LinkPulse's AWS overlay swaps the image, adds a pull secret, patches BASE_URL and adds the Ingress.

## CI/CD

Q: CI vs CD?
A: Continuous integration: every change is automatically built and tested. Continuous delivery/deployment: every change that passes is releasable / released automatically.

Q: Walk me through your pipeline.
A: Lint and tests on every merge request (tests against a Postgres service). On main: build an image tagged with the commit SHA, push to ECR, refresh the pull secret, run the migration Job, roll out API and worker, wait, smoke-test /health.

Q: Why tag images with commit SHAs?
A: Every running version maps to exact code, and rollbacks target an exact build. "latest" is ambiguous.

Q: How do you keep secrets out of reach of untrusted code?
A: Protected variables only reach protected branches; main is protected and needs a green pipeline to merge. MR pipelines run without credentials.

Q: Least privilege in your pipeline?
A: The CI IAM user can only push to one ECR repository; CI has its own revocable SSH key; host key pinned.

Q: How would you improve the deploy mechanism?
A: Pull-based deploys (GitLab Agent or Argo CD) so no inbound access is needed; OIDC instead of long-lived keys.

## AWS and security

Q: What's a VPC? A security group?
A: Your private network in AWS; a stateful firewall attached to resources. LinkPulse: the database group allows 5432 only from the EC2 group.

Q: Why a security-group-to-security-group rule instead of an IP?
A: It follows whichever instances are in the group, even when IPs change.

Q: Why is the database not public?
A: No internet address means nothing outside the VPC can even try to connect.

Q: IAM users vs roles?
A: Users have long-lived credentials; roles are assumed and give temporary credentials. Prefer roles (and OIDC for CI) where possible.

Q: What does an IAM policy deny by default?
A: Everything; explicit Deny overrides Allow.

Q: How did you keep a password out of shell history?
A: `read -s` into a variable, use it, then `unset`.

Q: What is an Elastic IP for?
A: A fixed public address that survives stop/start.

## Reliability and operations

Q: What happens if each dependency fails?
A: Redis: slower redirects, no rate limiting. Kafka: redirects fine, events buffered and possibly lost after a long outage. Postgres: new links fail, cached links still redirect, pods go not-ready. Worker: counts lag, then catch up.

Q: What would you monitor?
A: Request rate, error rate and latency (p50/p95/p99) for redirects; cache hit ratio; consumer lag; pod restarts; database connections and CPU.

Q: Graceful shutdown?
A: On SIGTERM, the API flushes buffered Kafka events; the worker finishes its batch and commits offsets before exiting.

## About the project

Q: Why did you build this?
A: To get hands-on with the full lifecycle of a backend service, from code to production, the way a team would: event-driven processing, caching, containers, Kubernetes, CI/CD and AWS.

Q: What would you do differently?
A: Start with Terraform for AWS, add observability earlier, use a pull-based deploy, and test the worker's save logic directly.

Q: What was the hardest part?
A: The deployment environment, not the code: diagnosing the out-of-memory instance that looked like a network problem, and getting the pipeline's secrets and SSH setup right without weakening security.
