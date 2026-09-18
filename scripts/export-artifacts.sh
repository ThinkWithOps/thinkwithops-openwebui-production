#!/usr/bin/env bash
# Allowlist export: never dump Secrets, logs, Helm release values, or user data.
source "$(dirname -- "$0")/lib-playground.sh"
require_context
require_owned_release
need python3
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="docs/evidence/v1/export-$stamp"
mkdir -p "$out"
k get deployments,statefulsets,pods,services,pvc,configmaps -l "app.kubernetes.io/instance=$RELEASE" -o json |
  python3 scripts/sanitize-evidence.py > "$out/cluster-summary.json"
git rev-parse HEAD > "$out/source-commit.txt"
cp helm-chart/Chart.yaml helm-chart/Chart.lock "$out/"
printf 'UTC %s\nConfiguration: chart pins included; credentials and session URLs excluded.\n' "$stamp" > "$out/README.txt"
printf 'Export created: %s\nReview before sharing; download before session expiry. This is NOT a data backup.\n' "$out"
