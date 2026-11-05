# 0004. One image for API, worker and migrations

Status: accepted

## Context
The API, the worker and the migration step share all code and dependencies.

## Decision
Build one image. The default command runs the API; the worker and migrations override it (`python -m worker.main`, `alembic upgrade head`). Migrations run as a separate one-shot step (Compose service, Kubernetes Job), not at API startup.

## Consequences
- One build, one scan, one tag per commit; all parts always run the same code version.
- Running migrations once, before rollout, avoids races between multiple API replicas.
- Migrations must stay backward-compatible because old and new pods overlap during a rolling update.
