import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
RENDERED = ROOT / "_local/rendered-playground.yaml"

class ConfigurationGuards(unittest.TestCase):
    def setUp(self):
        self.objects = list(yaml.safe_load_all(RENDERED.read_text(encoding="utf-8-sig")))

    def validate(self, deployment=False):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.yaml"
            path.write_text(yaml.safe_dump_all(self.objects), encoding="utf-8")
            command = [sys.executable, str(ROOT / "scripts/validate-config.py"), str(path)]
            if deployment:
                command.append("--deployment")
            return subprocess.run(command, capture_output=True, text=True)

    def app(self):
        return next(o for o in self.objects if o and o["kind"] == "Deployment" and o["metadata"]["name"] == "openwebui")

    def test_placeholder_cannot_deploy(self):
        result = self.validate(deployment=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("approved model endpoint", result.stderr)

    def test_resolved_session_can_pass_deployment_gate(self):
        container = self.app()["spec"]["template"]["spec"]["containers"][0]
        next(e for e in container["env"] if e["name"] == "OPENAI_API_BASE_URL")["value"] = "https://models.example.com/v1"
        for obj in self.objects:
            if obj and obj["kind"] == "PersistentVolumeClaim":
                obj["spec"]["storageClassName"] = "verified-test-class"
            if obj and obj["kind"] == "ConfigMap":
                obj["data"].update(DEFAULT_MODELS="approved-test-model", WEBUI_URL="https://chat.example.com")
        self.assertEqual(self.validate(deployment=True).returncode, 0)

    def test_ci_is_validation_only(self):
        directory = ROOT / ".github/workflows"
        workflows = list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))
        for path in workflows:
            workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(workflow.get("permissions"), {"contents": "read"})
            self.assertEqual(set(workflow["jobs"]), {"validate"})
            self.assertNotIn("secrets.", path.read_text(encoding="utf-8"))

    def test_plaintext_credential_rejected(self):
        env = self.app()["spec"]["template"]["spec"]["containers"][0]["env"]
        secret = next(e for e in env if e["name"] == "WEBUI_SECRET_KEY")
        secret.pop("valueFrom")
        secret["value"] = "test-secret-do-not-use"
        self.assertNotEqual(self.validate().returncode, 0)

    def test_second_replica_rejected(self):
        self.app()["spec"]["replicas"] = 2
        self.assertNotEqual(self.validate().returncode, 0)

    def test_missing_probe_rejected(self):
        del self.app()["spec"]["template"]["spec"]["containers"][0]["readinessProbe"]
        self.assertNotEqual(self.validate().returncode, 0)

    def test_duplicate_env_rejected(self):
        env = self.app()["spec"]["template"]["spec"]["containers"][0]["env"]
        env.append(env[0].copy())
        self.assertNotEqual(self.validate().returncode, 0)

    def test_export_discards_sensitive_values(self):
        resource = {"kind": "ConfigMap", "metadata": {"name": "openwebui-config", "annotations": {"secret": "CANARY-SECRET"}},
                    "data": {"WEBUI_AUTH": "True", "API_KEY": "CANARY-SECRET", "WEBUI_URL": "https://CANARY-PRIVATE"}}
        result = subprocess.run([sys.executable, str(ROOT / "scripts/sanitize-evidence.py")],
                                input=json.dumps({"items": [resource]}), capture_output=True, text=True, check=True)
        self.assertNotIn("CANARY", result.stdout)
        self.assertEqual(json.loads(result.stdout)["resources"][0]["config"], {"WEBUI_AUTH": "True"})

if __name__ == "__main__":
    unittest.main()
