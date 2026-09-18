# V1 playground storage

First inspect `kubectl get storageclass`, node allocatable resources and actual disk space. Prefer an existing supported dynamic provisioner. Set the same selected StorageClass for both PVCs through configure-playground.py.

If the raw kubeadm playground has no provisioner, the explicit fallback below creates **two local PVs on one worker**. No storage operator or cloud disk is provisioned. Local storage survives pod replacement on that worker, not worker/session loss. Capacity fields do not enforce filesystem quotas.

## Explicit local-PV setup

1. Inspect `kubectl get nodes --show-labels`. Select a Ready, schedulable worker with at least 10Gi free disk and enough CPU/RAM.
2. On **that worker's terminal/SSH session**, inspect and create only project-specific directories:

```bash
df -h /var/local
sudo mkdir -p /var/local/thinkwithops-openwebui/app /var/local/thinkwithops-openwebui/postgresql
sudo chown 999:999 /var/local/thinkwithops-openwebui/postgresql
sudo chmod 0700 /var/local/thinkwithops-openwebui/postgresql
sudo chmod 0755 /var/local/thinkwithops-openwebui/app
```

The application image runs with its upstream user defaults; PostgreSQL runs as UID/GID 999. Verify the selected provisioner supports the ownership/mount behavior.

3. In the kubectl terminal:

```bash
kubectl auth can-i create persistentvolumes
kubectl auth can-i create storageclasses.storage.k8s.io
cp helm-chart/local-pv.example.yaml _local/local-pv.yaml
# Edit both REPLACE_WORKER values to the selected kubernetes.io/hostname label.
# Inspect existing project-named resources; never overwrite unrelated resources.
kubectl get storageclass thinkwithops-local --ignore-not-found
kubectl get pv thinkwithops-openwebui-data thinkwithops-openwebui-postgresql --ignore-not-found
kubectl create -f _local/local-pv.yaml
export STORAGE_CLASS=thinkwithops-local
bash scripts/preflight.sh
```

Use `create` only once in a new session. If objects already exist, inspect/reuse them; do not delete or replace them blindly. Claim references are fixed to namespace `thinkwithops-openwebui` and PVCs `openwebui` and `openwebui-postgresql`. Node affinity keeps each consumer on the correct worker. WaitForFirstConsumer can leave claims Pending until the workloads are scheduled.

PV retain policy and Helm keep annotations help avoid accidental data loss but are not a backup. A Released PV needs deliberate recovery; do not wipe claimRef or delete directories as routine troubleshooting.

## Troubleshooting

```bash
kubectl -n thinkwithops-openwebui get pods,pvc
kubectl -n thinkwithops-openwebui describe pvc openwebui
kubectl -n thinkwithops-openwebui describe pvc openwebui-postgresql
kubectl -n thinkwithops-openwebui get events --sort-by=.lastTimestamp
```

Inspect output privately. Pending volumes commonly mean missing provisioner/PV, wrong class, insufficient disk, mismatched node affinity, or unschedulable worker. Do not remove control-plane taints or alter unrelated workloads to make the demo fit.
