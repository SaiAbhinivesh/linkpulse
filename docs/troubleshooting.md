# Troubleshooting

Real problems hit while building this project, grouped by where they show up. Each entry: the symptom you see, why it happens, and the fix.

## Local setup

### `role "linkpulse" does not exist` when the API connects to Postgres
- Why: another Postgres installed directly on your machine is listening on `localhost:5432` and answers first.
- Check: `lsof -nP -iTCP:5432 -sTCP:LISTEN` shows a `postgres` process besides Docker.
- Fix: the project maps Postgres to port 5433 to avoid this. Make sure `DATABASE_URL` uses `localhost:5433`.

### Commands fail with odd errors about extra arguments
- Example: `alembic: error: unrecognized arguments` or `error: pathspec 'part' did not match`.
- Why: curly quotes (“ ”) pasted from a chat, document or notes app. The shell only understands straight quotes (").
- Fix: retype the quotes in the terminal. On macOS, turn off System Settings > Keyboard > Text Input > Edit > "Use smart quotes and dashes".

### `ModuleNotFoundError: No module named 'api.something'`
- Why: the file name doesn't match the import exactly (e.g. `ate_limit.py`, `rate-limit.py`), or it's in the wrong folder.
- Fix: `ls api` and compare. `api.rate_limit` means the file `api/rate_limit.py`.
- Related: the package marker must be named `__init__.py` (two underscores each side), inside `api/`.

### `NameError: name 'Request' is not defined`
- Why: a name used in code wasn't imported.
- Fix: add the import. Run `ruff check .` before starting the server; rule F821 catches undefined names.

### The server hangs instead of failing after an import error
- Why: with `--reload`, uvicorn's watcher process keeps the port open even though the worker process crashed, so clients wait forever.
- Fix: read the uvicorn terminal for the traceback, fix it, and the reloader restarts.

### `pip install` fails building `confluent-kafka` or `psycopg`
- Why: Python is newer than the available prebuilt wheels.
- Fix: use Python 3.12 (`brew install python@3.12`, then `python3.12 -m venv .venv`).

### Tests fail: `database "linkpulse_test" does not exist`
- Why: Compose creates the test database only the first time the Postgres volume is created. An older volume from before that may not have it.
- Fix: `docker compose exec postgres createdb -U linkpulse linkpulse_test`, or reset everything with `docker compose down -v` and `docker compose up -d postgres` (this wipes local data).

### `Bind for 0.0.0.0:8000 failed: port is already allocated`
- Why: something else uses the port: an old `uvicorn` in another terminal, or a stack that's already up.
- Check: `lsof -nP -iTCP:8000 -sTCP:LISTEN` (same for 5433, 6380, 9092).
- Fix: stop that process, or `docker compose down` first.

## Docker and Kubernetes (local)

### `kubectl version --client` shows an old version
- Why: Docker Desktop ships its own kubectl in `/usr/local/bin`, and your shell remembered that path.
- Fix: `which -a kubectl`, then `hash -r` (or open a new terminal) so Homebrew's copy in `/opt/homebrew/bin` is used.

### `kubectl` changes the wrong cluster
- Why: each terminal has its own `KUBECONFIG`. Without it, kubectl uses the kind cluster; a pod "deleted from linkpulse namespace" ran on kind, not AWS.
- Fix: `kubectl config current-context` before any change. `default` is the AWS k3s cluster, `kind-linkpulse` is local.

### `kubectl logs job/migrate` says the Job is not found
- Why: `kubectl kustomize` only prints the rendered YAML; it doesn't deploy anything.
- Fix: `kubectl apply -k k8s/overlays/aws`.

### Kafka pod crashes on Kubernetes with odd configuration errors
- Why: Kubernetes injects `KAFKA_PORT`-style variables for the `kafka` Service, and the Kafka image treats every `KAFKA_*` variable as a broker setting.
- Fix: `enableServiceLinks: false` in the pod spec (already in `k8s/local/kafka.yaml`).

### Re-applying fails with "field is immutable" on the migrate Job
- Why: Jobs can't be updated once created.
- Fix: `kubectl delete job migrate` first. CI does this on every deploy.

### Warnings after `kubectl rollout undo` about `last-applied-configuration`
- Why: the live object was changed with imperative commands (`set image`, `undo`) after being created with `apply`.
- Fix: none needed right away. The next `kubectl apply` makes the cluster match the files again; treat git as the source of truth.

## AWS

### AWS CLI: `You must specify a region`
- Fix: `aws configure set region YOUR_REGION` (check with `aws configure get region`).

### `mv ~/Downloads/key.pem ~/.ssh/` says "Operation not permitted" (macOS)
- Why: macOS privacy protection; the terminal app has no access to Downloads.
- Fix: System Settings > Privacy & Security > Files & Folders > enable Downloads for Terminal or VS Code, then restart the app.

### `k3s: command not found` after launching EC2
- Why: the user data was pasted without its `#!/bin/bash` first line, so cloud-init didn't run it as a script.
- Check: `sudo cat /var/lib/cloud/instance/user-data.txt` and `sudo tail /var/log/cloud-init-output.log` on the instance.
- Fix: install k3s over SSH (see [deploy-to-aws.md](deploy-to-aws.md#6-ec2-instance-with-k3s)).

### kubectl to AWS: `TLS handshake timeout`, even through the SSH tunnel
- Why: the instance was too small (t3.micro, 1 GB). k3s used all memory, load average was above 5, and the API server stopped responding.
- Check: `ssh ... "nproc; free -m; uptime"`.
- Fix: stop the instance, change the type to `m7i-flex.large` (8 GB), start it. Lesson: when everything is slow, check memory and CPU before blaming the network.

### kubectl to port 6443 over the internet stalls after the TLS handshake
- Why: some networks mishandle traffic on unusual ports.
- Fix: use the SSH tunnel (port 22) and keep 6443 closed. It's also more secure.

### `psql` from a pod: `Connection refused` to the RDS address
- Why: the pod ran on the local kind cluster, which can't reach a private AWS address. On AWS a blocked security group gives a timeout, not "refused".
- Fix: switch `KUBECONFIG` to the AWS cluster and retry.

### The `psql` password prompt never appears
- Why: psql printed it before kubectl attached the terminal.
- Fix: just type or paste the password and press Enter.

### AWS CLI: `expired` or `Unable to locate credentials` after a while
- Why: an `aws login` session lasts up to 12 hours.
- Fix: run `aws login --region YOUR_REGION` again.

### Pods stuck in `ImagePullBackOff` after a manual `kubectl apply`
- Why: the `ecr-pull` Secret holds an ECR token that expires after 12 hours. CI refreshes it on every deploy; a manual apply doesn't.
- Fix: recreate it (the `kubectl create secret docker-registry ecr-pull ...` command in [deploy-to-aws.md](deploy-to-aws.md)), then `kubectl rollout restart deployment/api deployment/worker`.

### API pods show `0/1` Ready right after starting the instances
- Why: the readiness check needs Postgres, and RDS takes 5-10 minutes to become Available.
- Fix: wait. `aws rds describe-db-instances ... --query "DBInstances[].DBInstanceStatus"` should say `available`; the pods turn Ready on their own.

## GitLab CI

### `Unable to run pipeline: mapping values are not allowed in this context`
- Why: a script line contains `: ` (colon + space), which YAML reads as key/value.
- Fix: wrap the whole line in single quotes. Use Build > Pipeline editor to validate.

### Merge request pipeline shows only lint and test
- Not an error: build and deploy run only on `main`, where the protected variables exist.

### Two pipelines for the same commit
- Why: the branch was pushed before the merge request existed (branch pipeline), then the MR started its own.
- Not an error; later pushes run only the MR pipeline.

### `cp: can't stat '<IP> ssh-ed25519 AAAA...'`
- Why: `SSH_KNOWN_HOSTS` was created as type Variable, so it holds the text instead of a file path.
- Fix: edit the variable, set Type to File, retry the job.

### `Load key ...: error in libcrypto` then `Permission denied (publickey)`
- Why: the private key value is malformed, usually missing the final newline or the BEGIN/END lines.
- Fix: re-paste with `pbcopy < ~/.ssh/linkpulse-ci`, make sure there's an empty line after `-----END OPENSSH PRIVATE KEY-----`, keep Type = File. Alternative: store the key base64-encoded in a masked variable and decode it in the job.

### GitLab won't save a masked variable: "cannot contain whitespace characters"
- Why: multi-line values (keys, known_hosts) can't be masked.
- Fix: set Visibility to Visible and rely on Protected + File type.

### Containers on EC2 fail with `exec format error`
- Why: an ARM image (built on Apple Silicon) running on an Intel instance.
- Fix: `docker buildx build --platform linux/amd64 ...` for manual pushes. CI runners already build amd64.

### Every visitor shares one rate limit on AWS
- Why: behind Traefik, the client address is Traefik's.
- Fix: uvicorn's `--proxy-headers --forwarded-allow-ips "*"` (already in the Dockerfile) reads `X-Forwarded-For`.

### lint fails: `File would be reformatted --> docs/....md`
- Why: newer Ruff versions also format Python code blocks inside Markdown files, and CI installs the latest Ruff.
- Fix: run `ruff format .` locally (it fixes the docs too), commit, push. Upgrade your local Ruff (`pip install -U ruff`) so it matches CI.
