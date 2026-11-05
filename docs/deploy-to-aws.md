# Deploy to your own AWS account

This guide recreates the full AWS setup: images in ECR, Postgres on RDS, and a single EC2 instance running k3s (lightweight Kubernetes), deployed automatically by GitLab CI. Plan on 2 to 3 hours the first time.

Replace every `YOUR_...` value with your own. Pick one region and use it everywhere (the examples use `us-east-2`).

## Before you start

You need:

- The app running locally first (see [local-development.md](local-development.md)). If it doesn't work on your laptop, it won't work on AWS.
- An AWS account, signed in as an admin user (not the root user for daily work).
- AWS CLI v2, Docker Desktop and kubectl on your laptop.
- The repository on GitLab: the pipeline is GitLab CI. If you got the code from GitHub, create a GitLab project with New project > Import project > Repository by URL (or push your clone to an empty GitLab project). Free GitLab.com shared runners are enough.
- A password manager for the database password.

Costs: see below. When you're finished, follow "Tear down everything" in [operations.md](operations.md#tear-down-everything), or AWS keeps charging for disks and the IP address.

## What you'll create

| Resource | Name used here | Purpose |
| --- | --- | --- |
| ECR repository | `linkpulse` | Stores images |
| IAM user | `gitlab-ci` | Lets CI push to that one repository |
| RDS PostgreSQL 17 | `linkpulse-db` | The database (private) |
| Security groups | `linkpulse-ec2-sg`, `linkpulse-db-sg` | Firewalls |
| Elastic IP | | Fixed public address |
| Key pair | `linkpulse-key` | Your SSH access |
| EC2 instance | `linkpulse-k3s` | Runs k3s: API, worker, Redis, Kafka, Traefik |

```mermaid
flowchart LR
    U[Visitors] -->|HTTP :80| SG1
    subgraph VPC [Default VPC]
      subgraph SG1 [linkpulse-ec2-sg]
        EC2[EC2 + k3s]
      end
      subgraph SG2 [linkpulse-db-sg]
        RDS[(RDS)]
      end
    end
    EC2 -->|:5432, allowed by SG rule| RDS
    You[You / GitLab CI] -->|SSH :22| EC2
    EC2 -->|pull| ECR[(ECR)]
```

## Costs and limits

- Expect roughly a few dollars per day while EC2 and RDS run. Stop both when you're not using them (see [operations.md](operations.md)); stopped resources cost only cents for disks and the Elastic IP.
- Create a monthly budget alarm (Billing > Budgets > Monthly cost budget) before anything else.
- New AWS accounts on the Free plan can only launch certain EC2 types. Use `m7i-flex.large` (2 vCPU, 8 GB). Do not use `t3.micro` or `t3.small`: k3s plus Kafka needs several GB of memory, and with 1 GB the Kubernetes API becomes unresponsive.
- Accounts created with the newer sign-in experience ("projects") are limited to a single region and have a monthly spend limit. Keep everything in one region.

## 1. Command-line access

Install AWS CLI v2, then either `aws login` (console-based sign-in, CLI 2.32+) or `aws configure` with your own credentials. Set the default region:

```bash
aws configure set region YOUR_REGION
aws sts get-caller-identity
```

## 2. ECR repository

```bash
aws ecr create-repository --repository-name linkpulse --image-scanning-configuration scanOnPush=true
```

Note the `repositoryUri`: `YOUR_AWS_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/linkpulse`.

## 3. IAM user for CI (least privilege)

Edit `infra/iam/gitlab-ci-ecr-policy.json` so the repository ARN uses your region and account ID, then:

```bash
aws iam create-user --user-name gitlab-ci
aws iam put-user-policy --user-name gitlab-ci --policy-name linkpulse-ecr-push \
  --policy-document file://infra/iam/gitlab-ci-ecr-policy.json
aws iam create-access-key --user-name gitlab-ci
```

The policy allows only `ecr:GetAuthorizationToken` and push/pull on the `linkpulse` repository. Copy the access key straight into GitLab (step 11); never save it in a file.

## 4. RDS PostgreSQL

Choose a database password of 24+ letters and digits only (symbols break the connection URL). Store it in a password manager.

Console: RDS > Create database > Full configuration:

| Setting | Value |
| --- | --- |
| Engine | PostgreSQL 17.x, Extended Support off |
| Template | Free tier |
| Identifier / master user | `linkpulse-db` / `linkpulse` |
| Credentials | Self managed, your password |
| Instance | `db.t4g.micro` |
| Storage | gp3, 20 GiB, autoscaling off |
| Compute resource | Don't connect to an EC2 compute resource |
| Public access | No |
| Security group | Create new: `linkpulse-db-sg` |
| Monitoring | Database Insights Standard (7 days free); Enhanced Monitoring off |
| Initial database name | `linkpulse` (if empty, no database is created) |
| Backups | 1 day; deletion protection off for a learning setup |

When it shows Available, copy the endpoint (Connectivity & security tab): `YOUR_RDS_ENDPOINT`.

## 5. Networking

EC2 > Network & Security:

1. Elastic IPs > Allocate. This is `YOUR_EC2_IP`; it survives stop/start.
2. Security Groups > Create `linkpulse-ec2-sg` in the default VPC, inbound:
   - SSH (22) from My IP. In step 11 this becomes Anywhere so CI runners can deploy.
   - HTTP (80) from Anywhere-IPv4.
3. Edit `linkpulse-db-sg` inbound: delete existing rules, add PostgreSQL (5432) with source = the `linkpulse-ec2-sg` security group.
4. Key Pairs > Create `linkpulse-key` (ED25519, .pem), then:

   ```bash
   mv ~/Downloads/linkpulse-key.pem ~/.ssh/
   chmod 400 ~/.ssh/linkpulse-key.pem
   ```

   On macOS, if `mv` says "Operation not permitted", give your terminal (or VS Code) access to the Downloads folder in System Settings > Privacy & Security > Files & Folders.

## 6. EC2 instance with k3s

Put your Elastic IP into `infra/ec2/user-data.sh` (the `--tls-san` value). Then EC2 > Launch instance:

| Setting | Value |
| --- | --- |
| Name | `linkpulse-k3s` |
| AMI | Ubuntu Server 24.04 LTS, x86_64 |
| Type | `m7i-flex.large` (or any type with 4 GB+ RAM) |
| Key pair | `linkpulse-key` |
| Network | default VPC, auto-assign public IP on, security group `linkpulse-ec2-sg` |
| Storage | 20 GiB gp3 |
| User data | the whole of `infra/ec2/user-data.sh`, including the `#!/bin/bash` first line |

Then Elastic IPs > Associate with the instance.

Check k3s after 2-3 minutes:

```bash
EIP=YOUR_EC2_IP
ssh -i ~/.ssh/linkpulse-key.pem ubuntu@$EIP "sudo k3s kubectl get nodes"
```

If `k3s: command not found`, the boot script didn't run (check `/var/log/cloud-init-output.log`); install it manually:

```bash
ssh -i ~/.ssh/linkpulse-key.pem ubuntu@$EIP \
  "curl -sfL https://get.k3s.io | sudo INSTALL_K3S_EXEC='server --tls-san $EIP --write-kubeconfig-mode 644' sh -"
```

## 7. kubectl from your laptop (SSH tunnel)

The Kubernetes API (port 6443) stays closed to the internet. kubectl travels inside SSH instead.

```bash
ssh -i ~/.ssh/linkpulse-key.pem ubuntu@$EIP "sudo cat /etc/rancher/k3s/k3s.yaml" > ~/.kube/linkpulse-aws.yaml
sed -i '' "s#https://127.0.0.1:6443#https://127.0.0.1:16443#" ~/.kube/linkpulse-aws.yaml   # macOS sed
chmod 600 ~/.kube/linkpulse-aws.yaml
```

Every session:

```bash
# tab 1: keep running
ssh -i ~/.ssh/linkpulse-key.pem -N -L 16443:127.0.0.1:6443 ubuntu@YOUR_EC2_IP

# tab 2
export KUBECONFIG=~/.kube/linkpulse-aws.yaml
kubectl config current-context     # "default" = the AWS cluster
kubectl get nodes
```

## 8. Check the cluster can reach RDS

```bash
kubectl run pg-test --rm -it --image=postgres:17 --restart=Never -- \
  psql -h YOUR_RDS_ENDPOINT -U linkpulse -d linkpulse
# enter the password, then:  select version();   \q
```

A timeout means the `linkpulse-db-sg` rule is wrong.

## 9. First deploy by hand

Edit `k8s/overlays/aws/kustomization.yaml`: set `newName` to your ECR repository URI and the `BASE_URL` value to `http://YOUR_EC2_IP`.

```bash
kubectl apply -f k8s/namespace.yaml
kubectl config set-context --current --namespace=linkpulse

# App secret, without the password landing in shell history
read -s DB_PASSWORD
kubectl create secret generic linkpulse-secrets \
  --from-literal=DATABASE_URL="postgresql+psycopg://linkpulse:${DB_PASSWORD}@YOUR_RDS_ENDPOINT:5432/linkpulse"
unset DB_PASSWORD

# Image pull secret (valid 12 hours; CI refreshes it on every deploy)
kubectl create secret docker-registry ecr-pull \
  --docker-server=YOUR_AWS_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com \
  --docker-username=AWS --docker-password="$(aws ecr get-login-password)"

# Redis and Kafka (Postgres is RDS here)
kubectl apply -f k8s/local/redis.yaml -f k8s/local/kafka.yaml

# Build an amd64 image (needed on Apple Silicon) and push it
ECR=YOUR_AWS_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/linkpulse
aws ecr get-login-password | docker login --username AWS --password-stdin ${ECR%/linkpulse}
docker buildx build --platform linux/amd64 --build-arg APP_VERSION=manual-1 -t $ECR:manual-1 --push .

# Preview, then apply the overlay
kubectl kustomize k8s/overlays/aws
kubectl apply -k k8s/overlays/aws
kubectl get pods -w
kubectl logs job/migrate
```

Open `http://YOUR_EC2_IP/health` and `http://YOUR_EC2_IP/docs`.

## 10. Deploy key for CI

```bash
ssh-keygen -t ed25519 -f ~/.ssh/linkpulse-ci -N "" -C "gitlab-ci-deploy"
cat ~/.ssh/linkpulse-ci.pub | ssh -i ~/.ssh/linkpulse-key.pem ubuntu@YOUR_EC2_IP "cat >> ~/.ssh/authorized_keys"
ssh -i ~/.ssh/linkpulse-ci ubuntu@YOUR_EC2_IP "sudo k3s kubectl get nodes"   # test
ssh-keyscan -t ed25519 YOUR_EC2_IP                                         # for SSH_KNOWN_HOSTS
```

## 11. Connect GitLab CI

1. Add the CI/CD variables listed in [configuration.md](configuration.md#gitlab-cicd-variables-aws-deploys). Mind the types: `SSH_PRIVATE_KEY` and `SSH_KNOWN_HOSTS` are File variables; the key must end with a newline (`pbcopy < ~/.ssh/linkpulse-ci` copies it exactly).
2. Protect `main` (Settings > Repository > Protected branches) so protected variables reach only reviewed code.
3. Change the SSH rule in `linkpulse-ec2-sg` to Anywhere-IPv4. GitLab's shared runners have no fixed IPs. Login is key-only, and the CI key can be revoked by removing its line from `~/.ssh/authorized_keys`.
4. Merge to `main` and watch Build > Pipelines: lint, test, build, deploy.

```bash
curl http://YOUR_EC2_IP/health     # "version" = the merge commit's short SHA
```

## Files that contain your values

| File | What to set |
| --- | --- |
| `infra/iam/gitlab-ci-ecr-policy.json` | region and account ID in the repository ARN |
| `infra/ec2/user-data.sh` | Elastic IP after `--tls-san` |
| `k8s/overlays/aws/kustomization.yaml` | ECR repository URI (`newName`) and `BASE_URL` |

Everything else (passwords, keys, the RDS endpoint) lives in Kubernetes Secrets or GitLab variables, not in git.

## Next steps toward production

- EKS, MSK and ElastiCache instead of a single k3s node with in-cluster Kafka and Redis.
- GitLab Agent for Kubernetes or Argo CD (pull-based deploys, no inbound ports).
- OIDC federation instead of a long-lived IAM access key.
- Terraform for everything created by hand in this guide.
- HTTPS with a domain (Traefik + cert-manager or an AWS load balancer).
