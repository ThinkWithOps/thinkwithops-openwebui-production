#!/usr/bin/env python3
"""Create private credentials once and JSON-as-YAML session values; no values printed."""
import getpass
import json
import os
from pathlib import Path
import secrets
import subprocess
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "_local"
NS = "thinkwithops-openwebui"
os.umask(0o077)
PRIVATE.mkdir(exist_ok=True)

def kubectl(*args, **kwargs):
    return subprocess.run(["kubectl", "--request-timeout=30s", *args], check=True, **kwargs)

def prompt(label):
    value = input(label + ": ").strip()
    if not value or "\n" in value or "\r" in value:
        raise SystemExit("A nonempty single-line value is required.")
    return value

def private_write(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)

context = subprocess.check_output(["kubectl", "config", "current-context"], text=True).strip()
if not os.getenv("EXPECTED_CONTEXT") or context != os.environ["EXPECTED_CONTEXT"]:
    raise SystemExit("Set EXPECTED_CONTEXT to the inspected playground context.")
base = prompt("Approved OpenAI-compatible HTTPS API base URL")
parts = urlsplit(base)
if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.hostname.endswith(".invalid"):
    raise SystemExit("Use an approved HTTPS base URL without credentials, query, or fragment.")
model = prompt("Approved chat model ID")
storage = prompt("Verified StorageClass name")
url = prompt("Browser URL from View Port or verified ingress (no query token)")
browser = urlsplit(url)
if browser.scheme != "https" or not browser.hostname or browser.query or browser.fragment or browser.username or browser.password:
    raise SystemExit("Use the HTTPS browser URL supplied by the playground or verified ingress.")
values = {
    "postgresql": {"storageClass": storage},
    "open-webui": {"openaiBaseApiUrl": base, "persistence": {"storageClass": storage}},
    "appConfig": {"DEFAULT_MODELS": model, "WEBUI_URL": url, "WEBUI_SESSION_COOKIE_SECURE": "True"},
}
private_write(PRIVATE / "values-session.yaml", values)
# Namespace create is idempotent; never changes an existing namespace.
result = subprocess.run(["kubectl", "get", "namespace", NS], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
if result.returncode:
    kubectl("create", "namespace", NS)
exists = subprocess.run(["kubectl", "-n", NS, "get", "secret", "openwebui-secrets"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
if exists.returncode == 0:
    print("Existing Secret preserved. Session values written; credentials unchanged.")
    raise SystemExit(0)
path = PRIVATE / "secrets.json"
if path.exists():
    secret = json.loads(path.read_text(encoding="utf-8"))
    if secret.get("metadata", {}).get("namespace") != NS or secret.get("metadata", {}).get("name") != "openwebui-secrets":
        raise SystemExit("Private secret backup has unexpected identity.")
else:
    pvc = subprocess.check_output(
        ["kubectl", "-n", NS, "get", "pvc", "openwebui-postgresql", "--ignore-not-found", "-o", "name"],
        text=True).strip()
    if pvc:
        raise SystemExit("Database PVC already exists. Restore the original Secret; refusing to generate new credentials.")
    email = prompt("Bootstrap admin email")
    password = getpass.getpass("Bootstrap admin password (at least 12 characters): ")
    if len(password) < 12:
        raise SystemExit("Password must have at least 12 characters.")
    api_key = getpass.getpass("Approved endpoint API key (not echoed): ").strip()
    if not api_key:
        raise SystemExit("API key required. No provider or free access is assumed.")
    db_password, redis_password = secrets.token_hex(32), secrets.token_hex(32)
    data = {
        "WEBUI_SECRET_KEY": secrets.token_hex(32),
        "WEBUI_ADMIN_EMAIL": email, "WEBUI_ADMIN_PASSWORD": password,
        "OPENAI_API_KEY": api_key, "POSTGRES_PASSWORD": db_password,
        "DATABASE_URL": f"postgresql://openwebui:{db_password}@openwebui-postgresql:5432/openwebui",
        "REDIS_PASSWORD": redis_password,
        "REDIS_URL": f"redis://:{redis_password}@openwebui-redis:6379/0",
        "redis.conf": f'bind 0.0.0.0\nprotected-mode yes\nrequirepass {redis_password}\nsave ""\nappendonly no\nmaxmemory 128mb\nmaxmemory-policy noeviction\n',
    }
    secret = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "openwebui-secrets", "namespace": NS}, "type": "Opaque", "stringData": data}
    private_write(path, secret)
# stdin prevents credentials from appearing in shell history / process arguments.
kubectl("create", "-f", "-", input=json.dumps(secret), text=True, stdout=subprocess.DEVNULL)
print("Secret created. Keep _local/secrets.json encrypted outside the playground before expiry.")
