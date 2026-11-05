# 0005. k3s on a single EC2 instance instead of EKS

Status: accepted (for a learning setup)

## Context
The goal is to learn and demonstrate Kubernetes on AWS at low cost. EKS charges for the control plane on top of nodes; MSK and ElastiCache add more fixed cost. New free-plan accounts also restrict instance types.

## Decision
Run k3s on one `m7i-flex.large` EC2 instance, with Redis and Kafka inside the cluster. Keep Postgres on RDS, because the database is the one component worth handing to a managed service.

## Consequences
- Same Kubernetes concepts and manifests, a fraction of the cost.
- Single point of failure: one node, one Kafka broker, Kafka data inside the pod.
- Production path: EKS (multiple nodes), MSK, ElastiCache, RDS Multi-AZ.
