#!/usr/bin/env bash
source "$(dirname -- "$0")/lib-playground.sh"
require_context
require_owned_release
for tool in python3 curl; do need "$tool"; done
mkdir -p docs/evidence/v1
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
evidence="docs/evidence/v1/verify-$stamp.txt"
# Only controlled check labels go to evidence; no API bodies or credentials.
record() { printf '%s\n' "$*" | tee -a "$evidence"; }
trap 'record "FAILED: verification stopped; inspect private terminal output"' ERR
record "UTC $stamp"
for workload in statefulset/openwebui-postgresql deployment/openwebui-redis deployment/openwebui; do
  k rollout status "$workload" --timeout=15m
  record "PASS: $workload rollout"
done
k get pvc openwebui openwebui-postgresql -o json | python3 -c '
import json,sys
items=json.load(sys.stdin)["items"]
assert len(items)==2 and all(x["status"]["phase"]=="Bound" for x in items), "PVC not Bound"
'
record 'PASS: application and PostgreSQL PVCs Bound'
k exec statefulset/openwebui-postgresql -- sh -ec 'PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -U openwebui -d openwebui -v ON_ERROR_STOP=1 -Atc "SELECT 1"' >/dev/null
record 'PASS: PostgreSQL authenticated SELECT 1'
k exec deployment/openwebui-redis -- sh -ec 'test "$(redis-cli ping)" = PONG'
record 'PASS: Redis authenticated PING'
# App network namespace, not the operator shell.
k exec deployment/openwebui -- python -c 'import os,redis; assert redis.Redis.from_url(os.environ["REDIS_URL"]).ping()'
record 'PASS: application-to-Redis connectivity'
python3 scripts/smoke-chat.py --evidence "$evidence"
record 'NOT RUN: browser rendering, TLS chain, streaming and WebSocket upgrade; complete docs/verification.md'
