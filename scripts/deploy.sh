#!/usr/bin/env bash
source "$(dirname -- "$0")/lib-playground.sh"
require_context
for tool in helm python3; do need "$tool"; done
[[ "${PREFLIGHT_REVIEWED:-}" == yes ]] || die "Run preflight.sh and set PREFLIGHT_REVIEWED=yes after reviewing capacity/storage/access"
[[ -f _local/values-session.yaml ]] || die "Run python3 scripts/configure-playground.py first"
k get secret openwebui-secrets >/dev/null
# Reject missing keys without printing any secret values.
k get secret openwebui-secrets -o json | python3 -c '
import json,sys
d=json.load(sys.stdin)["data"]
required=["WEBUI_SECRET_KEY","DATABASE_URL","POSTGRES_PASSWORD","REDIS_PASSWORD","REDIS_URL","redis.conf","OPENAI_API_KEY","WEBUI_ADMIN_EMAIL","WEBUI_ADMIN_PASSWORD"]
if not all(d.get(k) for k in required): raise SystemExit("Required secret keys missing")
'
args=(-f helm-chart/values-playground.yaml -f _local/values-session.yaml)
if [[ -n "${INGRESS_VALUES:-}" ]]; then args+=(-f "$INGRESS_VALUES"); fi
build_dependencies
helm lint helm-chart "${args[@]}" --strict
helm template "$RELEASE" helm-chart -n "$NAMESPACE" "${args[@]}" > _local/rendered.yaml
python3 scripts/validate-config.py _local/rendered.yaml --deployment
# Server admission validation does not install workloads.
kubectl -n "$NAMESPACE" apply --dry-run=server -f _local/rendered.yaml >/dev/null
helm upgrade --install "$RELEASE" helm-chart -n "$NAMESPACE" "${args[@]}" --wait --timeout 20m
# ConfigMap env changes need an explicit restart (chart does not hash our ConfigMap).
k rollout restart deployment/openwebui
k rollout status deployment/openwebui --timeout=15m
echo 'Deployment ready. Run bash scripts/verify.sh; browser/chat persistence remain unverified until then.'
