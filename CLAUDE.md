# CLAUDE.md

Guidance for AI coding assistants (and humans) working in this repo.

## What this is

LinkPulse: a URL shortener with click analytics. FastAPI API + Kafka stats worker + Postgres + Redis, packaged as one Docker image, run on Kubernetes (kind locally, k3s on AWS), deployed by GitLab CI. Full docs: `docs/README.md`.

## Commands

```bash
source .venv/bin/activate              # Python 3.12 virtualenv
docker compose up --build              # whole stack on http://localhost:8000
docker compose up -d postgres          # just what the tests need
pytest -v                              # tests (needs Postgres on localhost:5433)
ruff check . --fix && ruff format .    # lint + format (CI runs both with --check)
alembic revision --autogenerate -m "msg"   # new migration; review the file
alembic upgrade head                   # apply migrations
uvicorn api.main:app --reload          # API on the host, uses .env
python -m worker.main                  # worker on the host, uses .env
kubectl kustomize k8s/overlays/aws     # render the AWS manifests
```

## Layout

- `api/main.py` routes. `config.py` settings (pydantic-settings, env vars). `db.py` engine + `get_db`. `models.py` tables. `schemas.py` request/response models. `cache.py` Redis. `rate_limit.py` per-IP limiter. `events.py` Kafka producer. `codes.py`, `timing.py` helpers.
- `worker/main.py` Kafka consumer (group `stats-workers`).
- `migrations/` Alembic. `tests/` pytest (`conftest.py` swaps DB, Redis, Kafka).
- `k8s/app/` Kustomize base. `k8s/local/` Postgres/Redis/Kafka for clusters. `k8s/overlays/aws/` AWS differences.
- `infra/` IAM policy and EC2 boot script. `docs/` knowledge centre.

## Rules that matter

- One image, three uses: API (default CMD), worker (`python -m worker.main`), migrations (`alembic upgrade head`).
- Route order: `/{code}` must stay the last route in `api/main.py`, or it swallows other paths.
- Postgres is the source of truth. Redis and Kafka failures must degrade, not crash (see `cache.py`, `events.py`, `rate_limit.py`).
- `/health` must not touch dependencies (liveness). `/ready` checks Postgres (readiness).
- Worker processing must stay idempotent: record `event_id` in `processed_events` in the same transaction as the count upsert; commit Kafka offsets only after the DB commit.
- In tests, patch names where they are used (e.g. `api.main.publish_click`, `api.rate_limit.redis_client`), not where they are defined.
- Settings must come from environment variables. No hardcoded hosts or credentials in code.

## Gotchas

- In `.gitlab-ci.yml`, quote any script line containing `: ` (YAML treats it as a mapping).
- Images built on Apple Silicon for EC2 need `--platform linux/amd64`. CI runners are amd64 already.
- Kubernetes Jobs are immutable: delete `job/migrate` before re-applying.
- Kafka in Kubernetes needs `enableServiceLinks: false` (injected `KAFKA_*` env vars confuse the broker).
- Local ports: Postgres 5433, Redis 6380, Kafka 9092, API 8000.

## Do not

- Commit secrets, `.env`, kubeconfigs or `.pem` files.
