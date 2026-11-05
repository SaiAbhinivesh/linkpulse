# The pitch

Adjust the wording until it sounds like you. Keep the numbers.

## 30 seconds ("tell me about a recent project")

I built LinkPulse, a URL shortener with click analytics, to get hands-on with production backend patterns end to end. It's a FastAPI service with Postgres, Redis for caching and rate limiting, and Kafka for click events, which a separate worker turns into daily stats. It runs on Kubernetes, and a GitLab CI pipeline tests every merge request and deploys every merge to AWS automatically, with zero-downtime rollouts.

## 2 minutes ("walk me through it")

1. What it does. You create a short link, visitors get redirected, and you can see click stats per day.

2. The interesting design decision. Redirects are the hot path, so I kept them minimal. The API checks Redis first, and only goes to Postgres on a miss. That took redirects from about 25 ms to about 3 ms. Counting the click does not happen in the request: the API drops an event onto Kafka and returns the redirect immediately. A worker consumes those events in batches and updates the counts.

3. Correctness. Kafka gives at-least-once delivery, so a crash can redeliver events. I made the worker idempotent: every event has an ID, the worker records IDs in the same database transaction as the count update, and commits Kafka offsets only after that. I proved it by rewinding the consumer group and replaying the whole topic: 8 events reprocessed, 0 counted twice.

4. Resilience. If Redis is down, redirects still work, just slower. If Kafka is down, redirects still work and events are buffered. Liveness and readiness are separate, so a database outage takes pods out of traffic without Kubernetes restarting them in a loop.

5. Delivery. Everything is one Docker image used three ways: API, worker and migrations. Locally it runs on Docker Compose or kind. On AWS it runs on k3s on EC2, with RDS for Postgres and images in ECR. Every merge to main builds an image tagged with the commit SHA, runs migrations as a Kubernetes Job, does a rolling update, and smoke-tests the public endpoint. The AWS credentials are only available to pipelines on the protected main branch.

## 5 minutes (deep dive with a whiteboard)

Draw, left to right:

```
Browser -> Traefik -> API (x2) -> Redis
                         |  \---> Postgres (RDS)
                         v
                      Kafka (clicks, 3 partitions) -> Worker -> Postgres
```

Then walk through, in this order, and stop wherever they ask questions:

1. The redirect path: route match, cache-aside lookup, 307 (not 301, so browsers don't cache it and every click is counted), publish event, return.
2. Link creation: rate limit via Redis INCR + EXPIRE, Pydantic validation, insert, and the unique index handling code collisions instead of a check-then-insert race.
3. The worker: consumer group, batch consume, dedupe table plus upsert in one transaction, manual offset commit, graceful shutdown on SIGTERM.
4. Kubernetes: Deployments, Services, ConfigMap and Secret, migrations as a Job, readiness on /ready vs liveness on /health, maxUnavailable 0.
5. CI/CD: MR pipelines run lint and tests against real Postgres; main builds, pushes to ECR, deploys over SSH, smoke tests. Protected variables, a least-privilege IAM user, a dedicated deploy key with a pinned host key.
6. What I'd change for production (always end here): EKS, MSK and ElastiCache instead of one k3s node; GitLab Agent or Argo CD instead of SSH; OIDC instead of long-lived keys; Terraform; HTTPS; observability with metrics and tracing; pruning the dedupe table.

## Likely follow-ups to have ready

- "Why Kafka and not just a database counter?" See [question-bank.md](question-bank.md#kafka-and-event-driven-design).
- "What was the hardest part?" The undersized EC2 instance ([troubleshooting.md](../troubleshooting.md#kubectl-to-aws-tls-handshake-timeout-even-through-the-ssh-tunnel)).
- "What would break first at 100x traffic?" Postgres write load from the worker and a single Kafka broker; see [system-design.md](system-design.md#scaling-it).
- "What did you learn?" Separating the fast path from the slow path, and designing for failure of each dependency.
