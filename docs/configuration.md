# Configuration

All settings are environment variables, read by `api/config.py` (pydantic-settings). The same code runs everywhere; only the environment changes. When running directly on your machine, values come from `.env`.

## Application settings

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `DATABASE_URL` | yes | | SQLAlchemy URL, e.g. `postgresql+psycopg://user:password@host:5432/linkpulse` |
| `REDIS_URL` | yes | | e.g. `redis://host:6379/0` |
| `KAFKA_BOOTSTRAP_SERVERS` | no | `localhost:9092` | Kafka broker(s), comma-separated |
| `CLICKS_TOPIC` | no | `clicks` | Topic for click events |
| `BASE_URL` | no | `http://localhost:8000` | Prefix for `short_url` in responses |
| `CACHE_TTL_SECONDS` | no | `3600` | How long redirects stay cached in Redis |
| `CREATE_RATE_LIMIT_PER_MINUTE` | no | `10` | Link creations allowed per IP per minute |
| `APP_VERSION` | no | `dev` | Reported by `/health`; set at build time |

Test-only:

| Variable | Default | Purpose |
| --- | --- | --- |
| `TEST_DATABASE_URL` | `postgresql+psycopg://linkpulse:linkpulse@localhost:5433/linkpulse_test` | Database pytest uses |

Keep passwords to letters and digits. Characters like `@ : / ? #` have special meaning inside a URL and break `DATABASE_URL` unless URL-encoded.

## Where each value comes from

| Environment | Non-secret settings | `DATABASE_URL` |
| --- | --- | --- |
| Your machine | `.env` (copy of `.env.example`) | `.env` |
| Docker Compose | `x-app-env` block in `compose.yaml` | `compose.yaml` (local-only password) |
| kind | ConfigMap `k8s/app/configmap.yaml` | Secret `linkpulse-secrets`, created with `kubectl create secret` |
| AWS | ConfigMap, with `BASE_URL` patched in `k8s/overlays/aws/kustomization.yaml` | Secret `linkpulse-secrets` pointing at RDS |
| GitLab CI tests | `variables:` of the `test` job | the `test` job's Postgres service |

`APP_VERSION` is a Docker build argument (`--build-arg APP_VERSION=...`). CI sets it to the commit's short SHA.

## Runtime flags (Dockerfile)

The API runs as:

```
uvicorn api.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips "*"
```

- `--host 0.0.0.0`: listen on all interfaces, required inside a container.
- `--proxy-headers --forwarded-allow-ips "*"`: take the client IP from `X-Forwarded-For` set by Traefik, so rate limiting is per visitor. Safe here only because pods are reachable solely through the ingress.

## Kubernetes objects

| Name | Kind | Holds |
| --- | --- | --- |
| `linkpulse-config` | ConfigMap | `REDIS_URL`, `KAFKA_BOOTSTRAP_SERVERS`, `BASE_URL` |
| `linkpulse-secrets` | Secret | `DATABASE_URL` |
| `postgres-auth` | Secret | `POSTGRES_USER/PASSWORD/DB` for the in-cluster Postgres (kind only) |
| `ecr-pull` | Secret (docker-registry) | ECR login for pulling images (AWS only, refreshed by CI) |

Kubernetes Secrets are base64-encoded, not encrypted. Access control is what protects them.

## GitLab CI/CD variables (AWS deploys)

Set under Settings > CI/CD > Variables. All are Protected (only `main` pipelines receive them).

| Key | Type | Masked | Value |
| --- | --- | --- | --- |
| `AWS_ACCESS_KEY_ID` | Variable | yes | Access key of the CI IAM user |
| `AWS_SECRET_ACCESS_KEY` | Variable | yes | Its secret |
| `AWS_DEFAULT_REGION` | Variable | no | e.g. `us-east-2` |
| `ECR_REGISTRY` | Variable | no | `YOUR_AWS_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com` |
| `EC2_HOST` | Variable | no | `YOUR_EC2_IP` |
| `SSH_PRIVATE_KEY` | File | no (multi-line) | Private key of the CI deploy key, ending with a newline |
| `SSH_KNOWN_HOSTS` | File | no | Output of `ssh-keyscan -t ed25519 YOUR_EC2_IP` |
