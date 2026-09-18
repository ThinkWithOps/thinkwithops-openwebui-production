# Backup and fresh-session recovery

A PVC survives pod replacement while its underlying storage remains. A playground may erase nodes, volumes and credentials at expiry. Git and the non-secret evidence export cannot recover users, uploaded files or history.

## Before expiry

Start while at least 15–20 minutes remain; extend the session if necessary. Complete the backup before ending the lab.

1. Prepare an age encryption identity on a trusted machine outside the playground. Preserve the private identity there; transfer only its public `age1...` recipient to the playground.
2. Install `age` in the playground using its supported package manager if missing. Keep the shell in the project root with EXPECTED_CONTEXT set.
3. Run:

```bash
export AGE_RECIPIENT='REPLACE_WITH_YOUR_PUBLIC_AGE_RECIPIENT'
bash scripts/backup.sh
bash scripts/export-artifacts.sh
```

Backup briefly scales **only Open WebUI** to zero to stop application writes. A temporary pod mounts the application PVC; PostgreSQL stays running. It captures a logical database dump, full app volume, the original Kubernetes Secret (including WEBUI_SECRET_KEY), session values, chart pins and source commit. These are encrypted together with age. Redis is transient and excluded.

The exit handler deletes the temporary pod and attempts to return the application to one replica even on failure. On failure, private partial data remains under ignored `_local/backup.*` for diagnosis; it must not be shared or committed. On success only the encrypted archive remains. Private temporary files are mode 0600/0700, but encryption at rest for the playground itself is not claimed.

4. **Download the encrypted archive and sanitized evidence to storage outside the lab environment before expiry.** Use the active playground's supported download/transfer method. Do not assume Git stores these ignored files.
5. Verify the downloaded file's hash matches the original (`sha256sum <archive>`) and confirm decryption with the saved age identity on the trusted machine. Do not expose the plaintext archive in public storage.

Keep the original signing key and DB credentials. Losing WEBUI_SECRET_KEY invalidates sessions and may make encrypted application credentials unusable. TLS private keys are not included: provision the new session's TLS Secret separately if using ingress.

## Fresh-session restore

Restore only into a **new namespace with empty application and database volumes**. The script refuses an existing namespace. It never drops an existing database or uses `pg_restore --clean`.

1. Start a new standalone playground; transfer/clone the same source version and backup. Install Helm/Python validation requirements/age as in README.
2. Run preflight and recreate storage if necessary. Existing cluster context, node names, hostname, timer and browser URL may differ.
3. Prepare `_local/values-session.yaml` directly with this JSON (valid YAML), filling real non-secret settings. **Do not run configure-playground.py**, since it creates the namespace and a new secret.

```json
{
  "postgresql": {"storageClass": "REPLACE_WITH_VERIFIED_CLASS"},
  "open-webui": {
    "openaiBaseApiUrl": "https://REPLACE_APPROVED_ENDPOINT/v1",
    "persistence": {"storageClass": "REPLACE_WITH_VERIFIED_CLASS"}
  },
  "appConfig": {
    "DEFAULT_MODELS": "REPLACE_APPROVED_MODEL_ID",
    "WEBUI_URL": "https://REPLACE_SESSION_BROWSER_HOST",
    "WEBUI_SESSION_COOKIE_SECURE": "True"
  }
}
```

4. Temporarily provide the age private identity through a protected file outside Git. Set:

```bash
export EXPECTED_CONTEXT='REPLACE_NEW_PLAYGROUND_CONTEXT'
export PREFLIGHT_REVIEWED=yes
export BACKUP_FILE='/private/path/openwebui-backup.tar.age'
export AGE_IDENTITY='/private/path/age-identity.txt'
bash scripts/restore.sh
bash scripts/verify.sh
```

The restore script verifies chart/lock equality, decrypts into private ignored staging, restores the original Secret, starts PostgreSQL/Redis with app replicas zero, refuses nonempty data, restores DB/files, removes the maintenance pod, then starts one application replica. It uses current session values. Do not change DB major version or app/chart pin during restore.

For ingress, restore first through the default View Port route, then create the new TLS Secret and apply the ingress overlay. This avoids depending on an uncreated Secret during namespace bootstrap.

5. Sign in with the **old** user credentials and inspect the **old** backed-up chats and uploads in the browser. A newly created smoke conversation alone does not prove backup recovery. Record actual results in evidence/v1.
6. Remove the temporary identity from the playground when done. Failed restores remain stopped or partially populated for inspection; do not blindly rerun into that namespace.

## Failure handling

- Backup fails: verify the application returned to one replica; retain original PVCs. No cluster deletion is part of this workflow.
- Decryption fails: obtain the matching age private identity. The archive is not recoverable without it.
- Wrong chart/lock: restore with the original source first; upgrade separately afterward.
- Disk ownership or scheduler failure: inspect PVC/node affinity and UID 999 permissions; follow storage.md.
- Expired provider API key: rotate it deliberately after restoring. Do not replace DB credentials/signing key casually.
- No externally downloaded backup before expiry: configuration can be redeployed, but prior users/history/files may be lost.

**Restore drill status: NOT RUN.** These scripts are implementation artifacts, not evidence of successful recovery.
