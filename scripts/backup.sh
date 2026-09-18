#!/usr/bin/env bash
# Creates an encrypted, consistent backup during a short application outage.
source "$(dirname -- "$0")/lib-playground.sh"
require_context
require_owned_release
for tool in age tar; do need "$tool"; done
: "${AGE_RECIPIENT:?Set AGE_RECIPIENT to an age public recipient whose private key is saved outside the playground}"
[[ -f _local/values-session.yaml ]] || die "Session values missing"
[[ "$(k get deployment openwebui -o jsonpath='{.spec.replicas}')" == 1 ]] || die "Backup expects one running application replica"
[[ "$(k get pod openwebui-maintenance --ignore-not-found -o name)" == "" ]] || die "Maintenance pod already exists; inspect before retrying"
tmp="$(mktemp -d "$ROOT/_local/backup.XXXXXX")"
out="$ROOT/_local/openwebui-$(date -u +%Y%m%dT%H%M%SZ).tar.age"
created=no
cleanup() {
  local rc=$?
  trap - EXIT
  if [[ "$created" == yes ]]; then k delete pod openwebui-maintenance --wait=true --timeout=90s || true; fi
  k scale deployment/openwebui --replicas=1 || true
  k rollout status deployment/openwebui --timeout=15m || true
  if [[ "$rc" == 0 ]]; then
    rm -rf -- "$tmp"
  else
    echo "Backup failed. Private partial files retained at $tmp; app resume was attempted." >&2
  fi
  exit "$rc"
}
trap cleanup EXIT
k scale deployment/openwebui --replicas=0
k wait --for=delete pod -l 'app.kubernetes.io/instance=openwebui,app.kubernetes.io/component=open-webui' --timeout=180s
kubectl create -f scripts/maintenance-pod.yaml
created=yes
k wait --for=condition=Ready pod/openwebui-maintenance --timeout=180s
k exec statefulset/openwebui-postgresql -- sh -ec 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h 127.0.0.1 -U openwebui -d openwebui -Fc --no-owner --no-acl' > "$tmp/postgresql.dump"
# Binary streams stay in shell redirection, not terminal output.
k exec pod/openwebui-maintenance -- tar -C /data -czf - . > "$tmp/app-data.tar.gz"
k get secret openwebui-secrets -o json > "$tmp/secret.json"
cp _local/values-session.yaml "$tmp/values-session.yaml"
[[ -z "${INGRESS_VALUES:-}" ]] || cp "$INGRESS_VALUES" "$tmp/values-ingress.yaml"
cp helm-chart/Chart.yaml helm-chart/Chart.lock "$tmp/"
git rev-parse HEAD > "$tmp/source-commit.txt"
tar -C "$tmp" -cf - . | age -r "$AGE_RECIPIENT" -o "$out"
test -s "$out"
printf 'Encrypted backup: %s\nDownload it now; keep the age private key elsewhere. Restore test remains required.\n' "$out"
