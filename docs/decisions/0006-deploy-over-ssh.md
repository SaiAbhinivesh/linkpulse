# 0006. Deploy over SSH instead of exposing the Kubernetes API

Status: accepted

## Context
CI needs to apply manifests to the cluster. Exposing the Kubernetes API (port 6443) to the internet is risky, and in practice it was unreliable from some networks. GitLab shared runners have no fixed IP, so any inbound rule for them must be open to all addresses.

## Decision
CI renders manifests locally and pipes them over SSH to `k3s kubectl apply` on the instance. Humans use an SSH tunnel for kubectl. Port 6443 stays closed. CI has its own key, and the server's host key is pinned through `SSH_KNOWN_HOSTS`.

## Consequences
- Only ports 22 (key-only login) and 80 are open.
- Port 22 open to the internet attracts scanning; mitigated by key-only auth and a revocable CI key.
- Production path: GitLab Agent for Kubernetes or Argo CD, where the cluster pulls changes and no inbound ports are needed.
