#!/usr/bin/env bash
source "$(dirname -- "$0")/lib-playground.sh"
need helm
need python3
build_dependencies
for profile in playground ingress; do
  args=(-f helm-chart/values-playground.yaml)
  [[ "$profile" != ingress ]] || args+=(-f helm-chart/values-ingress.example.yaml)
  helm lint helm-chart "${args[@]}" --strict
  helm template openwebui helm-chart -n "$NAMESPACE" "${args[@]}" > "_local/rendered-$profile.yaml"
  python3 scripts/validate-config.py "_local/rendered-$profile.yaml"
done
for file in scripts/{lib-playground,preflight,deploy,verify,export-artifacts,validate,backup,restore}.sh; do bash -n "$file"; done
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
