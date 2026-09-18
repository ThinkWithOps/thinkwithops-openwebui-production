# V1 acceptance verification

## Current status

Static results are in evidence/v1. Live cluster, provider, browser, restart and fresh-session restore checks have not been run by the implementation agent. Record only actual observations; failed or blocked checks must remain visible.

## Automated checks in the playground

```bash
bash scripts/verify.sh
bash scripts/export-artifacts.sh
```

Enter an existing test user's credentials at the private prompts. Use the bootstrap admin for initial testing or create a dedicated user through Admin Panel. Self-signup stays disabled. The script makes a real request to the approved model, saves the resulting conversation via the chat API, records no content, writes a harmless uploads-volume marker, replaces only the app pod, and rechecks user ID, old token, exact stored chat and volume marker.

The smoke test leaves its test conversation and marker for inspection. It does not delete user data. A non-streaming API test cannot substitute for browser streaming/WebSocket verification.

## Browser checks (required)

1. Open the actual session HTTPS URL. Verify the certificate is trusted and the hostname matches.
2. Sign in with the test user. Select the approved model. Send a harmless question and observe a real streaming reply.
3. Upload a harmless uniquely named test file where the UI permits it. Verify upload/download. Document content processing is outside V1; do not confuse an unsupported RAG feature with raw storage persistence.
4. In browser developer tools, inspect Network for the Socket.IO `/ws/socket.io/` WebSocket upgrade (HTTP 101), authenticated connection and continued traffic. A login page alone is insufficient.
5. Note the conversation title and upload. Run `bash scripts/verify.sh`, which restarts only Open WebUI. Reconnect port-forward if used.
6. Refresh/sign in as the same user. Confirm the original browser conversation and uploaded file remain readable/downloadable.
7. Record results and a redacted screenshot in `docs/evidence/v1/`. Hide email, API keys, cookies, tokens, private hostnames and chat contents.

## Evidence record

Create a timestamped Markdown file with: UTC timestamp, source commit plus uncommitted-change status, app/chart versions, selected playground type, each check's PASS/FAIL/BLOCKED/NOT RUN result, sanitized output links, and known limitations. Keep exact URL and identities in ignored `_local/access.txt`.

`verify-*.txt` contains actual check labels. `export-*/cluster-summary.json` includes only allowed resource/status fields. Export intentionally excludes logs, env vars, annotations, IPs, secrets and complete Helm values. Inspect artifacts before sharing.

## Completion gate

V1 is verified only when workload/database readiness, real provider response, browser sign-in/chat, WebSocket access and app-only restart persistence all pass. Fresh-session restore is a separate recovery claim: record it only after restoring and checking previously backed-up history/uploads. Do not claim expiry survival from a pod-restart test.

A proposed release tag is `v1.0-openwebui-k8s-deployment`. Commit/push/tag/PR require explicit approval; scripts never perform those operations.
