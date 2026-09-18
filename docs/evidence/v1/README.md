# V1 verification evidence

## Status

| Check | Result |
|---|---|
| Official chart/app pairing and upstream templates inspected | PASS |
| Helm 3.19.0 lint/render/configuration guards, both access profiles | PASS ? static-validation.txt |
| Bash/Python syntax and 8 configuration/export guard tests | PASS ? static-validation.txt |
| Cluster capacity/storage/permissions/session access | BLOCKED — no playground session accessible |
| Workload/DB/Redis readiness | NOT RUN |
| Provider/model selection | BLOCKED — approved provider/model not supplied |
| Actual API chat and saved history | NOT RUN |
| Browser HTTPS/WebSockets/streaming | NOT RUN |
| App-only pod restart persistence | NOT RUN |
| Encrypted backup/fresh-session restore | NOT RUN |
| GitHub Actions execution | NOT RUN — workflow created only |
| Runner-to-cluster deployment | NOT VERIFIED / NOT ENABLED |

Static output must not be presented as live runtime evidence. Generated real results belong here only after the corresponding commands run. Raw logs, tokens, passwords, chat text, kubeconfigs and private session URLs belong outside Git.

No commit, push, tag, release or PR was created. Proposed tag after verification and approval: `v1.0-openwebui-k8s-deployment`.
