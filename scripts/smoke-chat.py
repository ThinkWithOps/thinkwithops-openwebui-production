#!/usr/bin/env python3
"""Authenticated real chat, explicit save, app-only restart, user/chat/file persistence."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid

NS = "thinkwithops-openwebui"
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--evidence", required=True)
args = parser.parse_args()
def record(message):
    print(message, flush=True)
    with open(args.evidence, "a", encoding="utf-8") as stream:
        stream.write(message + "\n")
def k(*args):
    return subprocess.check_output(["kubectl", "--request-timeout=30s", "-n", NS, *args], text=True).strip()
def uid(name):
    return k("get", "pods", "-l", "app.kubernetes.io/instance=openwebui,app.kubernetes.io/component=" + name,
             "-o", "jsonpath={.items[0].metadata.uid}")
email = input("Existing test user/admin email: ").strip()
password = getpass.getpass("Password (never recorded): ")
values = json.loads((ROOT / "_local/values-session.yaml").read_text())
model = values["appConfig"]["DEFAULT_MODELS"]
user_uid, db_uid, redis_uid = uid("open-webui"), uid("postgresql"), uid("redis")
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
token = None
forward = None
def start_forward():
    global forward
    forward = subprocess.Popen(["kubectl", "-n", NS, "port-forward", "--address=127.0.0.1", "service/openwebui", f"{port}:80"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        if forward.poll() is not None:
            raise RuntimeError("Port-forward exited")
        try:
            request("/health/db")
            return
        except (OSError, urllib.error.URLError):
            time.sleep(1)
    raise RuntimeError("Health timeout")
def stop_forward():
    if forward is not None and forward.poll() is None:
        forward.terminate()
        forward.wait(timeout=10)
def request(path, data=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(f"http://127.0.0.1:{port}" + path,
                                 data=None if data is None else json.dumps(data).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=180) as response:
        return json.load(response)
try:
    start_forward()
    auth = request("/api/v1/auths/signin", {"email": email, "password": password})
    token = auth["token"]
    identity = auth["id"]
    record("PASS: authenticated sign-in (identity redacted)")
    models = request("/api/models")
    if model not in [item["id"] for item in models["data"]]:
        raise RuntimeError("Approved model absent from accessible models")
    answer = request("/api/chat/completions", {"model": model, "stream": False,
                     "messages": [{"role": "user", "content": "Reply with a short greeting for a deployment smoke test."}]})
    content = answer["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Model returned no assistant text")
    record("PASS: real model response through Open WebUI (content redacted)")
    prompt_id, answer_id = str(uuid.uuid4()), str(uuid.uuid4())
    messages = [
        {"id": prompt_id, "parentId": None, "childrenIds": [answer_id], "role": "user",
         "content": "Reply with a short greeting for a deployment smoke test.", "timestamp": int(time.time()), "models": [model]},
        {"id": answer_id, "parentId": prompt_id, "childrenIds": [], "role": "assistant",
         "content": content, "model": model, "done": True, "timestamp": int(time.time())},
    ]
    chat = {"title": "V1 deployment persistence smoke", "models": [model], "messages": messages,
            "history": {"messages": {m["id"]: m for m in messages}, "currentId": answer_id}, "params": {}}
    saved = request("/api/v1/chats/new", {"chat": chat})
    chat_id = saved["id"]
    before = request("/api/v1/chats/" + chat_id)["chat"]
    fingerprint = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
    marker = str(uuid.uuid4())
    marker_path = "/app/backend/data/uploads/v1-persistence-" + marker + ".txt"
    k("exec", "deployment/openwebui", "--", "python", "-c",
      "from pathlib import Path; import sys; p=Path(sys.argv[1]); p.parent.mkdir(exist_ok=True); p.write_text(sys.argv[2])", marker_path, marker)
    record("PASS: real response saved to chat history; uploads-volume marker written")
    stop_forward()
    k("rollout", "restart", "deployment/openwebui")
    subprocess.run(["kubectl", "-n", NS, "rollout", "status", "deployment/openwebui", "--timeout=15m"], check=True)
    start_forward()
    # Old token must still work, exercising stable WEBUI_SECRET_KEY.
    after = request("/api/v1/chats/" + chat_id)["chat"]
    if hashlib.sha256(json.dumps(after, sort_keys=True).encode()).hexdigest() != fingerprint:
        raise RuntimeError("Saved chat changed after restart")
    auth_after = request("/api/v1/auths/signin", {"email": email, "password": password})
    if auth_after["id"] != identity:
        raise RuntimeError("User identity changed")
    k("exec", "deployment/openwebui", "--", "python", "-c",
      "from pathlib import Path; import sys; assert Path(sys.argv[1]).read_text()==sys.argv[2]", marker_path, marker)
    if uid("open-webui") == user_uid or uid("postgresql") != db_uid or uid("redis") != redis_uid:
        raise RuntimeError("Pod identities do not prove an app-only restart")
    record("PASS: app pod replaced; PostgreSQL and Redis pod UIDs unchanged")
    record("PASS: user identity, old auth token, saved chat and uploads-volume marker survived")
    record("NOTE: volume marker is a filesystem test; browser upload/download still requires manual check")
except Exception as error:
    # Do not print server bodies, request headers, passwords or chat content.
    record("FAIL: chat/persistence verification (" + type(error).__name__ + "); no success claimed")
    raise SystemExit(1) from None
finally:
    stop_forward()
