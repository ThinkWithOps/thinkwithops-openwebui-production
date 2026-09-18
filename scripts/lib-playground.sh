#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
NAMESPACE=thinkwithops-openwebui
RELEASE=openwebui
export NAMESPACE RELEASE
mkdir -p _local
umask 077
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null || die "Missing prerequisite: $1"; }
k() { kubectl --request-timeout=30s -n "$NAMESPACE" "$@"; }
require_context() {
  need kubectl
  : "${EXPECTED_CONTEXT:?Set EXPECTED_CONTEXT to the inspected playground context}"
  [[ "$(kubectl config current-context)" == "$EXPECTED_CONTEXT" ]] || die "Context differs from EXPECTED_CONTEXT"
}
require_owned_release() {
  [[ "$(k get deployment openwebui -o jsonpath='{.metadata.annotations.meta\.helm\.sh/release-name}')" == "$RELEASE" ]] || die "Application is not owned by this Helm release"
}

build_dependencies() {
  # Isolate Helm repository metadata from unrelated local repositories.
  export HELM_REPOSITORY_CONFIG="$ROOT/_local/helm-repositories.yaml"
  export HELM_REPOSITORY_CACHE="$ROOT/_local/helm-cache"
  mkdir -p "$HELM_REPOSITORY_CACHE"
  helm repo add thinkwithops-openwebui https://helm.openwebui.com --force-update
  helm dependency build helm-chart --skip-refresh
}
