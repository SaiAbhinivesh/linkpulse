# 0007. Kustomize overlays for environment differences

Status: accepted

## Context
Local (kind) and AWS need the same app manifests with a few differences: image location and tag, image pull secret, public base URL, and an Ingress.

## Decision
`k8s/app/` is a Kustomize base used as-is locally. `k8s/overlays/aws/` references it and adds only the differences (image override, JSON patches, ingress). CI changes only `newTag`.

## Consequences
- No duplicated YAML; a change to the base reaches every environment.
- Built into kubectl (`kubectl apply -k`, `kubectl kustomize`), no extra tool.
- For many environments or heavy templating, Helm would be the alternative.
