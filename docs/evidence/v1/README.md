# V1 verification evidence

## Status

| Check | Result |
|---|---|
| Official chart/app pairing and upstream templates inspected | PASS |
| Helm 3.19.0 lint/render/configuration guards, both access profiles | PASS ? static-validation.txt |
| Bash/Python syntax and 8 configuration/export guard tests | PASS ? static-validation.txt |
| Cluster capacity/storage/permissions/session access | PASS — live run; local-PV fallback used |
| Workload/DB/Redis readiness | PASS — live run |
| Provider/model selection | PASS — Groq OpenAI-compatible endpoint; `openai/gpt-oss-20b` |
| Actual API chat and saved history | PASS — live run |
| Browser HTTPS/WebSockets/streaming | PASS — live run |
| App-only pod restart persistence | PASS — live run; DB/Redis pod UIDs unchanged |
| Encrypted backup | PASS — live run |
| Fresh-session restore | PASS — live run |
| GitHub Actions execution | NOT RUN — workflow created only |
| Runner-to-cluster deployment | NOT VERIFIED / NOT ENABLED |

Static output must not be presented as live runtime evidence. Generated real results belong here only after the corresponding commands run. Raw logs, tokens, passwords, chat text, kubeconfigs and private session URLs belong outside Git.

No commit, push, tag, release or PR was created. Proposed tag after verification and approval: `v1.0-openwebui-k8s-deployment`.
