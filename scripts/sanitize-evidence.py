#!/usr/bin/env python3
"""Allowlist actual state; exclude annotations, env, endpoints, IPs, logs and identity."""
import json
import sys
from datetime import datetime, timezone

source = json.load(sys.stdin)
result = {"captured_at": datetime.now(timezone.utc).isoformat(), "resources": []}
for obj in source["items"]:
    kind = obj["kind"]
    item = {"kind": kind, "name": obj["metadata"]["name"]}
    spec, status = obj.get("spec", {}), obj.get("status", {})
    if kind in ("Deployment", "StatefulSet"):
        item.update(replicas=spec.get("replicas"), ready_replicas=status.get("readyReplicas", 0))
        item["containers"] = [{"name": c["name"], "image": c["image"], "resources": c.get("resources", {})}
                              for c in spec["template"]["spec"]["containers"]]
    elif kind == "Pod":
        item["phase"] = status.get("phase")
        item["containers"] = [{"name": c["name"], "ready": c["ready"], "restarts": c["restartCount"]}
                              for c in status.get("containerStatuses", [])]
    elif kind == "PersistentVolumeClaim":
        item.update(phase=status.get("phase"), capacity=status.get("capacity"), access_modes=spec.get("accessModes"))
    elif kind == "Service":
        item["type"] = spec["type"]
        item["ports"] = [{k: p[k] for k in ("port", "targetPort", "nodePort") if k in p} for p in spec["ports"]]
    elif kind == "ConfigMap":
        item["config"] = {key: obj["data"][key] for key in (
            "WEBUI_AUTH", "ENABLE_SIGNUP", "ENABLE_PERSISTENT_CONFIG", "UVICORN_WORKERS", "ENABLE_DB_MIGRATIONS")
            if key in obj.get("data", {})}
    result["resources"].append(item)
print(json.dumps(result, indent=2))
