import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from helpers import RepoCase
from loop_runtime.common import save, load

BUNDLE = Path(__file__).resolve().parents[1]


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="loop installation 中文 ")
        self.base = Path(self.tmp.name).resolve()
        self.home = self.base / "claude-home"; self.home.mkdir()
        self.project = self.base / "existing project"; self.project.mkdir()
        self.env = dict(os.environ, CLAUDE_HOME=str(self.home), PYTHON_BIN=sys.executable, SKIP_SPECIFY_CLI="1", PYTHONDONTWRITEBYTECODE="1")

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, args, cwd=None):
        r = subprocess.run(args, cwd=cwd or BUNDLE, env=self.env, text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def global_install(self, mode="strict"):
        return self.call([sys.executable, str(BUNDLE / "runtime/global_installer.py.md"), "--bundle-root", str(BUNDLE), "--claude-home", str(self.home), "--platform-mode", mode])

    def test_offline_shell_install_config_preservation_and_idempotence(self):
        original = {"custom-setting": {"example": "keep-me"}, "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo existing-hook"}]}]}}
        (self.home / "settings.json").write_text(json.dumps(original))
        (self.home / "CLAUDE.md").write_text("My existing project preferences.\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.project)], check=True)
        self.call(["sh", "install.sh", "all", str(self.project)])
        settings = json.loads((self.home / "settings.json").read_text())
        self.assertEqual(settings["custom-setting"], original["custom-setting"])
        self.assertEqual(settings["hooks"]["Stop"], original["hooks"]["Stop"])
        self.assertTrue(settings["sandbox"]["enabled"])
        script = self.project / ".specify/scripts/loopctl.py"
        output = self.call([sys.executable, str(script), "--root", str(self.project), "project", "init", "--project-id", "fixture"])
        self.assertTrue(json.loads(output)["initialized"])
        constitution = self.project / ".specify/memory/constitution.md"
        constitution.write_text("Established project rules.\n")
        policy = self.project / ".specify/loop-engineering/policy.json"
        custom = json.loads(policy.read_text()); custom["remediation"]["max_attempts"] = 4
        policy.write_text(json.dumps(custom))
        config = (self.project / ".specify/project.yaml").read_bytes()
        knowledge = (self.project / ".specify/knowledge/current.md").read_bytes()
        self.call(["sh", "install.sh", "all", str(self.project)])
        self.assertEqual(constitution.read_text(), "Established project rules.\n")
        self.assertEqual(json.loads(policy.read_text())["remediation"]["max_attempts"], 4)
        self.assertEqual((self.project / ".specify/project.yaml").read_bytes(), config)
        self.assertEqual((self.project / ".specify/knowledge/current.md").read_bytes(), knowledge)
        guidance = (self.home / "CLAUDE.md").read_text()
        self.assertIn("My existing project preferences", guidance)
        self.assertEqual(guidance.count("BEGIN PORTABLE SPEC KIT LOOP"), 1)
        self.assertTrue((self.project / ".specify/docs/INCREMENTAL-WORKFLOW.md").is_file())
        self.assertTrue((self.project / ".specify/docs/validation/summary.json").is_file())
        self.assertTrue((self.project / ".specify/templates/incremental/compatibility.example.json").is_file())
        for source in (BUNDLE / "runtime/loop_runtime").glob("*.py"):
            self.assertEqual(source.read_bytes(), (self.project / ".specify/scripts/loop_runtime" / source.name).read_bytes())
        self.call([str(self.project / ".specify/scripts/run-python.sh"), str(script), "--help"], self.project)

    def test_legacy_policy_migration_keeps_custom_fields_and_backup(self):
        self.global_install()
        p = self.project / ".specify/loop-engineering/policy.json"; p.parent.mkdir(parents=True)
        old = {"policy_version": "1.0.0", "custom": "keep", "principles": {"custom_boundary": True}, "loops": {"implementation": {"max_iterations": 9}}}
        p.write_text(json.dumps(old))
        self.call([sys.executable, str(self.home / "loop-engineering/bootstrap_project.py"), "--project-root", str(self.project), "--offline-init"])
        new = json.loads(p.read_text()); self.assertEqual(new["custom"], "keep")
        self.assertEqual(new["principles"], old["principles"])
        self.assertEqual(new["legacy_loop_limits"], old["loops"])
        self.assertEqual(new["remediation"]["max_attempts"], 3)
        backups = list((self.project / ".specify/loop-engineering/backups").rglob("policy.json"))
        self.assertTrue(any(json.loads(x.read_text()) == old for x in backups))

    def test_native_windows_settings_branch_without_claiming_windows_execution(self):
        self.global_install("native-windows")
        settings = json.loads((self.home / "settings.json").read_text())
        self.assertFalse(settings["sandbox"]["enabled"])
        self.assertEqual(settings["permissions"]["defaultMode"], "default")

    def test_invalid_project_does_not_create_it(self):
        self.global_install()
        missing = self.base / "missing"
        r = subprocess.run([sys.executable, str(self.home / "loop-engineering/bootstrap_project.py"), "--project-root", str(missing), "--offline-init"], env=self.env, capture_output=True)
        self.assertEqual(r.returncode, 2); self.assertFalse(missing.exists())


class InstalledCLITests(RepoCase):
    def test_installed_cli_runs_real_increment_and_rejects_stale_evidence(self):
        home = self.home / "isolated-claude"
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        def command(argv, expected=0):
            r = subprocess.run(argv, cwd=self.root, env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, expected, r.stdout + r.stderr)
            return json.loads(r.stdout)
        command([sys.executable, str(BUNDLE / "runtime/global_installer.py.md"), "--bundle-root", str(BUNDLE), "--claude-home", str(home)])
        command([sys.executable, str(home / "loop-engineering/bootstrap_project.py"), "--project-root", str(self.root), "--offline-init"])
        base = [str(self.root / ".specify/scripts/run-python.sh"), str(self.root / ".specify/scripts/loopctl.py"), "--root", str(self.root)]
        command(base + ["knowledge", "refresh"])
        command(base + ["context", "build", "--feature-dir", "specs/f"])
        ds = []
        for phase in ("requirements", "design"):
            prepared = command(base + ["gate", "prepare", phase, "--feature-dir", "specs/f"])
            ds.append({"id": phase, "scope": phase, "accepted": True, "actor": "fixture-developer", "source": "explicit integration test decision", "reason": "reviewed fixture", "unresolved_material_questions": [], "artifact_digest": prepared["artifact_digest"]})
            save(self.feature / "decisions.json", {"decisions": ds})
            command(base + ["gate", "evaluate", phase, "--feature-dir", "specs/f", "--record"])
        self.write("specs/f/tasks.md", "- [x] T001 implement US-001")
        command(base + ["selftests", "run", "--feature-dir", "specs/f"])
        result = command(base + ["gate", "evaluate", "implementation", "--feature-dir", "specs/f", "--record"])
        self.assertEqual(result["gate_decision"], "pass")
        save(self.root / ".specify/feature.json", {"feature_directory": "specs/f"})
        self.assertIn("implementation", command(base + ["status"])["gates"])
        self.write("src/app.py", "VALUE = 9\n")
        self.assertFalse(command(base + ["selftests", "check", "--feature-dir", "specs/f"], 1)["ok"])
