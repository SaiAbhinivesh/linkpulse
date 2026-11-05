# Operations

Day-to-day tasks for the AWS deployment. Local equivalents are in [local-development.md](local-development.md).

Before running kubectl against AWS:

```bash
# tab 1 (keep open)
ssh -i ~/.ssh/linkpulse-key.pem -N -L 16443:127.0.0.1:6443 ubuntu@YOUR_EC2_IP
# tab 2
export KUBECONFIG=~/.kube/linkpulse-aws.yaml
kubectl config current-context      # confirm you're on the AWS cluster before changing anything
```

## Stop and start (save money)

Stop at the end of a session:

```bash
aws rds stop-db-instance --db-instance-identifier linkpulse-db
aws ec2 stop-instances --instance-ids $(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=linkpulse-k3s" \
  --query "Reservations[].Instances[].InstanceId" --output text)
```

Start again (database first, it takes 5-10 minutes):

```bash
aws rds start-db-instance --db-instance-identifier linkpulse-db
aws ec2 start-instances --instance-ids $(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=linkpulse-k3s" \
  --query "Reservations[].Instances[].InstanceId" --output text)
```

Then reopen the SSH tunnel and check `kubectl get pods`. k3s restarts everything on boot; API pods stay 0/1 until RDS is available.

Notes:
- RDS starts itself again after 7 days stopped.
- Kafka keeps events inside its pod, so unconsumed events are lost when the instance restarts.

## Health

```bash
curl http://YOUR_EC2_IP/health           # {"status":"ok","version":"<commit sha>"}
curl http://YOUR_EC2_IP/ready
kubectl get pods
kubectl get endpointslices -l kubernetes.io/service-name=api
kubectl top pods                         # if metrics are available (k3s includes metrics-server)
```

## Logs

```bash
kubectl logs -l app=api --prefix -f      # both API pods
kubectl logs deploy/worker -f
kubectl logs job/migrate
kubectl describe pod POD_NAME            # Events section explains pull/start failures
```

## Consumer lag

```bash
kubectl exec deploy/kafka -- /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 --describe --group stats-workers
```

Growing `LAG` means the worker can't keep up. Scale workers (up to the number of partitions, 3):

```bash
kubectl scale deployment worker --replicas=2
```

## Deploying

Normal path: merge to `main`. See [ci-cd.md](ci-cd.md).

Manual deploy of a specific image tag (same steps as the pipeline).

Careful: `newTag` in `k8s/overlays/aws/kustomization.yaml` is only changed inside the CI job, never in git. Running `kubectl apply -k k8s/overlays/aws` without setting it first rolls the app back to whatever tag is in git (which may no longer exist in ECR). Find the live tag with `curl http://YOUR_EC2_IP/health` or `aws ecr list-images --repository-name linkpulse`.

```bash
sed -i '' "s/newTag: .*/newTag: TAG/" k8s/overlays/aws/kustomization.yaml   # macOS sed; TAG = an image tag in ECR
kubectl -n linkpulse delete job migrate --ignore-not-found
kubectl apply -k k8s/overlays/aws
kubectl rollout status deployment/api
```

## Rolling back

```bash
kubectl rollout history deployment/api
kubectl rollout undo deployment/api
kubectl rollout undo deployment/worker
```

Or Operate > Environments > production > re-deploy a previous deployment in GitLab.

Database migrations are not rolled back automatically. Keep migrations backward-compatible (add columns before using them, remove them only after no code uses them).

## Secrets

Rotate the database password:
1. RDS > Modify > new master password > Apply immediately.
2. Recreate the secret and restart the app:

```bash
kubectl delete secret linkpulse-secrets
read -s DB_PASSWORD
kubectl create secret generic linkpulse-secrets \
  --from-literal=DATABASE_URL="postgresql+psycopg://linkpulse:${DB_PASSWORD}@YOUR_RDS_ENDPOINT:5432/linkpulse"
unset DB_PASSWORD
kubectl rollout restart deployment/api deployment/worker
```

Rotate the CI AWS key: IAM > Users > gitlab-ci > Security credentials > create a new key, update the GitLab variables, delete the old key.

Revoke the CI SSH key: remove its line (`gitlab-ci-deploy`) from `/home/ubuntu/.ssh/authorized_keys` on the instance.

## Tear down everything

Goal: nothing left that charges. In this order, all in your one region:

1. RDS: delete `linkpulse-db`. Untick "Create final snapshot" and "Retain automated backups" (unless you want to keep the data; snapshots cost money). Takes 5-10 minutes; continue meanwhile.
2. EC2: terminate `linkpulse-k3s`. Its disk is deleted with it.
3. Elastic IPs: disassociate if still attached, then release. Every public IPv4 address is billed hourly, attached or not.
4. EC2 > Volumes and EC2 > Snapshots, RDS > Snapshots (Manual and System): all should be empty. Delete leftovers.
5. Security groups, after RDS is fully deleted: `linkpulse-db-sg` first, then `linkpulse-ec2-sg` (the first refers to the second). If AWS says a network interface is in use, RDS is still deleting: wait. Never delete the `default` group.
6. Key pairs: delete `linkpulse-key`, or keep it (free) to reuse the same `.pem` next time.
6. ECR: delete the `linkpulse` repository.
7. IAM: delete the `gitlab-ci` access key, its inline policy, then the user.
8. GitLab: delete all 7 CI/CD variables. The pipeline then skips build and deploy automatically.
9. Locally: remove `~/.kube/linkpulse-aws.yaml` and run `ssh-keygen -R YOUR_EC2_IP`. Compose and kind cost nothing; remove them only if you want the disk space (`docker compose down -v`, `kind delete cluster --name linkpulse`).
10. Check: these should print nothing, and the next day's bill (Billing and Cost Management > Bills) should show no growing lines.

```bash
aws ec2 describe-addresses --query "Addresses[].PublicIp" --output text
aws ec2 describe-volumes --query "Volumes[].VolumeId" --output text
aws rds describe-db-instances --query "DBInstances[].DBInstanceIdentifier" --output text
aws ecr describe-repositories --query "repositories[].repositoryName" --output text
```

To bring it back later, follow [deploy-to-aws.md](deploy-to-aws.md) again from step 2. The IP and RDS endpoint will be new: update the three files listed at the end of that guide and the GitLab variables.
