#!/usr/bin/env python3
"""Validate rendered Kubernetes configuration without contacting a cluster."""
import argparse
from collections import Counter
import re
import sys
import yaml

class UniqueLoader(yaml.SafeLoader):
    pass

def mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError("Duplicate YAML key: " + str(key))
        result[key] = loader.construct_object(value_node, deep=deep)
    return result
UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
parser = argparse.ArgumentParser()
parser.add_argument("manifest")
parser.add_argument("--deployment", action="store_true", help="Reject unresolved endpoint/access placeholders")
args = parser.parse_args()

def check(condition, message):
    if not condition:
        raise ValueError(message)

try:
    with open(args.manifest, encoding="utf-8-sig") as stream:
        objects = [x for x in yaml.load_all(stream, Loader=UniqueLoader) if x]
    by_id = {(o["kind"], o["metadata"]["name"]): o for o in objects}
    check(len(by_id) == len(objects), "Duplicate Kubernetes object identity")
    check(not any(o["kind"] == "Secret" for o in objects), "Secrets must be provisioned separately")
    workloads = [o for o in objects if o["kind"] in ("Deployment", "StatefulSet")]
    check(len(workloads) == 3, "V1 must render exactly three workloads")
    app = by_id["Deployment", "openwebui"]
    check(app["spec"]["replicas"] == 1, "V1 requires one Open WebUI replica")
    check(app["spec"]["strategy"]["type"] == "Recreate", "RWO deployment needs Recreate")
    for w in workloads:
        pod = w["spec"]["template"]["spec"]
        check(pod.get("automountServiceAccountToken") is False, "Workload token automount must be disabled")
        for c in pod.get("initContainers", []) + pod["containers"]:
            check(re.search(r":v?\d+\.\d+(?:\.\d+)?(?:[-@]|$)", c["image"]) is not None, "Image needs an exact version")
            check(c.get("resources", {}).get("requests") and c.get("resources", {}).get("limits"), "Missing resources")
            env = c.get("env", [])
            check(all(n == 1 for n in Counter(e["name"] for e in env).values()), "Duplicate environment variable")
        for c in pod["containers"]:
            check(all(c.get(p) for p in ("startupProbe", "readinessProbe", "livenessProbe")), "Missing probes")
    container = app["spec"]["template"]["spec"]["containers"][0]
    check(container["image"] == "ghcr.io/open-webui/open-webui:v0.11.3", "Unexpected app pin")
    env = {x["name"]: x for x in container["env"]}
    for key in ("WEBUI_SECRET_KEY", "DATABASE_URL", "OPENAI_API_KEY", "REDIS_URL", "WEBSOCKET_REDIS_URL",
                "WEBUI_ADMIN_EMAIL", "WEBUI_ADMIN_PASSWORD"):
        check(env[key].get("valueFrom", {}).get("secretKeyRef", {}).get("name") == "openwebui-secrets",
              key + " must use the existing Secret")
    check(env["WEBSOCKET_MANAGER"].get("value") == "redis", "Redis WebSocket manager required")
    check(env["ENABLE_WEBSOCKET_SUPPORT"].get("value") == "True", "WebSockets must be enabled")
    check(env["ENABLE_OLLAMA_API"].get("value") == "False", "Local model runtime must stay disabled")
    for name in ("openwebui", "openwebui-postgresql"):
        pvc = by_id["PersistentVolumeClaim", name]
        check(pvc["spec"]["accessModes"] == ["ReadWriteOnce"], "Expected RWO storage")
        check(pvc["metadata"]["annotations"]["helm.sh/resource-policy"] == "keep", "PVC retention missing")
    config = by_id["ConfigMap", "openwebui-config"]["data"]
    for key in config:
        check(not any(part in key for part in ("PASSWORD", "SECRET", "API_KEY", "TOKEN")), "Sensitive ConfigMap key")
    check(config.get("ENABLE_SIGNUP") == "False" and config.get("WEBUI_AUTH") == "True", "Authentication defaults unsafe")
    ingress = [o for o in objects if o["kind"] == "Ingress"]
    for obj in ingress:
        check(obj["spec"].get("tls"), "Ingress requires TLS")
    if args.deployment:
        check(env["OPENAI_API_BASE_URL"]["value"].startswith("https://") and not any(x in env["OPENAI_API_BASE_URL"]["value"] for x in (".invalid", "REPLACE")), "Select an approved model endpoint")
        check(config.get("DEFAULT_MODELS") and "REPLACE" not in config["DEFAULT_MODELS"], "Select an approved model")
        check(config.get("WEBUI_URL", "").startswith("https://") and not any(x in config["WEBUI_URL"] for x in (".invalid", "REPLACE")), "Set verified HTTPS browser URL")
        for name in ("openwebui", "openwebui-postgresql"):
            check(by_id["PersistentVolumeClaim", name]["spec"].get("storageClassName") and "REPLACE" not in by_id["PersistentVolumeClaim", name]["spec"]["storageClassName"], "Choose a verified storage class")
        for obj in ingress:
            check("REPLACE" not in obj["spec"].get("ingressClassName", ""), "Select an existing ingress class")
            check(all(".invalid" not in rule["host"] for rule in obj["spec"]["rules"]), "Set ingress DNS")
    print(f"PASS: {len(objects)} objects; 3 workloads; pins, probes, resources, secret refs, auth, persistence")
except (ValueError, KeyError, TypeError, yaml.YAMLError) as error:
    print("FAIL: " + str(error), file=sys.stderr)
    raise SystemExit(1) from None
