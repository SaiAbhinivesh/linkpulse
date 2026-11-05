# Knowledge Centre

Everything about how LinkPulse is built, run and deployed. Start with the page that matches what you want to do.

| I want to... | Read |
| --- | --- |
| Understand how the system works | [architecture.md](architecture.md) |
| Run it on my laptop | [local-development.md](local-development.md) |
| Know what every setting does | [configuration.md](configuration.md) |
| Deploy it to my own AWS account | [deploy-to-aws.md](deploy-to-aws.md) |
| Understand the pipeline | [ci-cd.md](ci-cd.md) |
| Start, stop, inspect, roll back | [operations.md](operations.md) |
| Fix something that broke | [troubleshooting.md](troubleshooting.md) |
| Build it myself, step by step | [learning-path.md](learning-path.md) |
| Know why it's built this way | [decisions/](decisions/) |
| Talk about it in a job interview | [interview/](interview/README.md) |

## Decision records

| # | Decision |
| --- | --- |
| 0001 | [Count clicks asynchronously through Kafka](decisions/0001-async-click-counting-with-kafka.md) |
| 0002 | [Idempotent consumer instead of exactly-once](decisions/0002-idempotent-consumer.md) |
| 0003 | [Cache-aside with graceful degradation](decisions/0003-cache-aside-graceful-degradation.md) |
| 0004 | [One image for API, worker and migrations](decisions/0004-one-image-three-roles.md) |
| 0005 | [k3s on a single EC2 instance instead of EKS](decisions/0005-k3s-on-ec2-instead-of-eks.md) |
| 0006 | [Deploy over SSH instead of exposing the Kubernetes API](decisions/0006-deploy-over-ssh.md) |
| 0007 | [Kustomize overlays for environment differences](decisions/0007-kustomize-overlays.md) |

## Conventions used in these docs

- Commands are meant to be run from the repository root unless a page says otherwise.
- Values you must replace are written in capitals with a `YOUR_` prefix, for example `YOUR_AWS_ACCOUNT_ID` or `YOUR_EC2_IP`.
- Local ports: API 8000, Postgres 5433, Redis 6380, Kafka 9092.
