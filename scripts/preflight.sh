#!/usr/bin/env bash
# Read-only inspection. Does not install storage, ingress, or cloud resources.
source "$(dirname -- "$0")/lib-playground.sh"
for tool in kubectl helm python3 curl; do need "$tool"; done
require_context
failed=0
inspect() {
  printf '\n> %s\n' "$*"
  if ! "$@"; then printf 'BLOCKED: inspection failed\n'; failed=1; fi
}
inspect kubectl version
inspect helm version --short
inspect kubectl get nodes -o wide
inspect kubectl get nodes -o 'custom-columns=NAME:.metadata.name,CPU:.status.allocatable.cpu,MEMORY:.status.allocatable.memory,EPHEMERAL:.status.allocatable.ephemeral-storage,TAINTS:.spec.taints'
inspect kubectl describe nodes
inspect kubectl get storageclasses
inspect kubectl get ingressclasses
inspect kubectl get pods -A
inspect kubectl get resourcequotas,limitranges -A
printf '\nOptional metrics (absence is not a failure):\n'
kubectl top nodes 2>/dev/null || printf 'NOT AVAILABLE: metrics-server\n'
for resource in deployments.apps statefulsets.apps services configmaps secrets persistentvolumeclaims serviceaccounts; do
  for verb in get list create patch update; do
    if [[ "$(k auth can-i "$verb" "$resource")" != yes ]]; then
      printf 'BLOCKED: %s %s in %s\n' "$verb" "$resource" "$NAMESPACE"; failed=1
    fi
  done
done
for operation in 'get pods' 'list pods' 'create pods' 'delete pods' 'create pods/exec' 'create pods/portforward' 'patch deployments/scale' 'update deployments/scale'; do
  read -r verb resource <<< "$operation"
  [[ "$(k auth can-i "$verb" "$resource")" == yes ]] || { printf 'BLOCKED: %s\n' "$operation"; failed=1; }
done
if ! k get namespace "$NAMESPACE" >/dev/null 2>&1; then
  [[ "$(kubectl auth can-i create namespaces)" == yes ]] || { echo 'BLOCKED: cannot create namespace'; failed=1; }
fi
printf '\nSession expires (operator supplied): %s\n' "${SESSION_EXPIRES_AT:-UNKNOWN}"
printf 'Browser access method (operator supplied): %s\n' "${PLAYGROUND_ACCESS_METHOD:-UNKNOWN}"
printf 'Storage selected (operator supplied): %s\n' "${STORAGE_CLASS:-UNKNOWN}"
[[ -n "${SESSION_EXPIRES_AT:-}" && -n "${PLAYGROUND_ACCESS_METHOD:-}" && "$SESSION_EXPIRES_AT" != *REPLACE* ]] || { echo 'BLOCKED: supply session expiry and access method from playground UI'; failed=1; }
if [[ -n "${STORAGE_CLASS:-}" ]]; then
  inspect kubectl get storageclass "$STORAGE_CLASS" -o yaml
else
  echo 'BLOCKED: select existing storage class or follow docs/storage.md'; failed=1
fi
python3 -c 'import yaml' || { echo 'BLOCKED: install scripts/requirements-validation.txt in a venv'; failed=1; }
echo 'Requests: 850m CPU / 1344Mi RAM total, plus Kubernetes system usage. PVCs: 10Gi total.'
echo 'Review free allocatable resources, quotas, node disk space, ingress controller health and session timer.'
echo 'Shell egress is not pod egress. Actual model connectivity is checked by verify.sh.'
exit "$failed"
