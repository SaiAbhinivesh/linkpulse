# Local development

Three ways to run LinkPulse on your laptop. Pick the one that matches what you're doing.

| Mode | Best for | Start with |
| --- | --- | --- |
| A. Docker Compose | Seeing the whole system run | `docker compose up --build` |
| B. Hybrid | Day-to-day coding with auto-reload | services in Compose, API and worker on your machine |
| C. kind (local Kubernetes) | Testing manifests, probes, rollouts | `kind create cluster` |

## Prerequisites

| Tool | Why | Install (macOS) |
| --- | --- | --- |
| Python 3.12 | App and tests | `brew install python@3.12` |
| Docker Desktop | Containers | docker.com |
| kubectl, kind | Mode C | `brew install kubectl kind` |
| AWS CLI v2 | Only for AWS work | `brew install awscli` |

Commands are written for macOS. Linux works the same (use your package manager; `sed -i` without the `''`). On Windows, use WSL2 with Docker Desktop's WSL integration.

Use Python 3.12 to match the Docker image. Newer Python versions may lack prebuilt wheels for `confluent-kafka` or `psycopg`.

## A. Docker Compose (whole stack)

```bash
docker compose up --build
```

Startup order is enforced with healthchecks: Postgres and Redis become healthy, Kafka starts, `kafka-init` creates the `clicks` topic, `migrate` runs Alembic, then `api` and `worker` start.

| Service | Port on your machine | Notes |
| --- | --- | --- |
| api | 8000 | http://localhost:8000/docs |
| postgres | 5433 | user/password/db `linkpulse`; also creates `linkpulse_test` |
| redis | 6380 | |
| kafka | 9092 | containers use `kafka:19092`, your machine uses `localhost:9092` |

Useful commands:

```bash
docker compose ps                          # status of every service
docker compose logs -f worker              # follow one service's logs
docker compose up -d --scale worker=2      # two workers sharing partitions
docker compose exec postgres psql -U linkpulse -c "\dt"
docker compose down                        # stop, keep data
docker compose down -v                     # stop and delete all data
```

## B. Hybrid (code on your machine, services in Compose)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env

docker compose up -d postgres redis kafka kafka-init
alembic upgrade head

uvicorn api.main:app --reload       # terminal 1
python -m worker.main               # terminal 2
```

`--reload` restarts the API whenever you save a `.py` file. It does not watch `.env`; restart manually after changing settings.

## Tests and linting

```bash
docker compose up -d postgres     # tests need the linkpulse_test database on port 5433
pytest -v
ruff check .
ruff format --check .             # or: ruff format .  to fix
```

How the tests are wired (`tests/conftest.py`):

- Each test gets freshly created tables in `linkpulse_test`, dropped afterwards.
- Redis is replaced with `fakeredis`; Kafka publishing is replaced with a function that records codes in a list.
- The app's `get_db` dependency is overridden to use the test database.

`TEST_DATABASE_URL` overrides the test database location (CI uses this).

## Database migrations

```bash
# after changing api/models.py
alembic revision --autogenerate -m "describe the change"
# read the new file in migrations/versions/ before applying
alembic upgrade head
alembic current          # which migration the database is on
alembic downgrade -1     # undo the last one
```

`migrations/env.py` reads `DATABASE_URL` from the same settings as the app.

## Inspecting the services

```bash
# Redis
docker compose exec redis redis-cli KEYS "link:*"
docker compose exec redis redis-cli TTL link:YOUR_CODE

# Kafka: watch click events arrive
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic clicks --from-beginning --property print.key=true

# Kafka: consumer lag
docker compose exec kafka /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 --describe --group stats-workers

# Kafka: replay everything (counts must not change)
docker compose stop worker
docker compose exec kafka /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 --group stats-workers \
  --reset-offsets --to-earliest --topic clicks --execute
docker compose start worker
```

## C. Local Kubernetes with kind

Stop Compose's `api` first if you plan to port-forward to 8000.

```bash
kind create cluster --name linkpulse
kubectl apply -f k8s/namespace.yaml
kubectl config set-context --current --namespace=linkpulse

# Secrets are created from the command line, never committed
kubectl create secret generic postgres-auth \
  --from-literal=POSTGRES_USER=linkpulse \
  --from-literal=POSTGRES_PASSWORD=linkpulse \
  --from-literal=POSTGRES_DB=linkpulse
kubectl create secret generic linkpulse-secrets \
  --from-literal=DATABASE_URL=postgresql+psycopg://linkpulse:linkpulse@postgres:5432/linkpulse

# Postgres, Redis, Kafka (+ topic Job)
kubectl apply -f k8s/local/
kubectl get pods -w       # wait for 1/1 and kafka-init Completed

# Build the image and hand it to kind
docker build -t linkpulse:local .
kind load docker-image linkpulse:local --name linkpulse

# App: ConfigMap, migrate Job, API (2 replicas), worker
kubectl apply -k k8s/app
kubectl port-forward svc/api 8000:8000
```

Things worth trying:

```bash
kubectl scale deployment api --replicas=4
kubectl delete pod -l app=api                 # watch them come back
kubectl scale deployment postgres --replicas=0  # API pods go 0/1 (readiness), no restarts
kubectl scale deployment postgres --replicas=1

# Release a new version and roll it back
docker build --build-arg APP_VERSION=v2 -t linkpulse:v2 .
kind load docker-image linkpulse:v2 --name linkpulse
kubectl set image deployment/api api=linkpulse:v2
kubectl rollout status deployment/api
kubectl rollout undo deployment/api
```

`kubectl set image` and `kubectl scale` change the live cluster only. The YAML in git is still the source of truth; the next `kubectl apply` puts things back.

Pause or remove the cluster:

```bash
docker stop linkpulse-control-plane      # pause (docker start ... to resume)
kind delete cluster --name linkpulse     # remove
```
