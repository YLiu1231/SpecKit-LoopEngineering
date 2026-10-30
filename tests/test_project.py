"""Executable scenarios for project inventory and context drift contracts."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from loop_runtime import project
from loop_runtime.common import load, save, read_record, write_record, file_digest


class ProjectContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "consumer"
        self.root.mkdir()
        self.git(self.root, "init", "-q")
        self.write(self.root, "src/app.py", "VALUE = 1\n")
        self.write(self.root, "tests/test_app.py", "assert True\n")
        self.write(self.root, "openapi.json", '{"openapi":"3.0.0"}\n')
        self.write(self.root, "specs/feature/spec.md", "# User stories\nKeep existing behavior.\n")
        self.commit(self.root)
        self.args = argparse.Namespace(root=str(self.root), project_id="consumer", main_branch=None, feature_dir="specs/feature", inputs=None)
        project.init_project(self.args)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def git(root, *args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True)
        return result.stdout.decode().strip()

    @staticmethod
    def write(root, relative, text):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, root):
        self.git(root, "add", ".")
        self.git(root, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")
        return self.git(root, "rev-parse", "HEAD")

    def producer(self):
        root = Path(self.temp.name) / "producer"
        root.mkdir()
        self.git(root, "init", "-q")
        self.write(root, "contract.md", "# Contract\nOld behavior preserved.\n")
        self.write(root, ".specify/project.yaml", json.dumps({"project_id": "producer", "schema_version": "1.0"}))
        self.commit(root)
        save(self.root / ".specify/local/workspace.json", {"projects": {"consumer": str(self.root), "producer": str(root)}})
        return root

    def set_inputs(self, value):
        save(self.root / ".specify/local/context-inputs.json", value)
        self.args.inputs = ".specify/local/context-inputs.json"

    def test_inventory_separates_discovery_from_execution(self):
        result = project.inspect_project(self.args)["inventory"]
        self.assertEqual(set(result["dimensions"]), {"business_and_function", "internal_architecture", "external_boundaries", "build_and_run", "selftests", "version_and_recovery", "knowledge_and_issues"})
        self.assertEqual(result["dimensions"]["selftests"]["execution_state"], "not_run")
        self.assertEqual(result["dimensions"]["external_boundaries"]["candidates"][0]["confirmation_state"], "unconfirmed")
        self.assertTrue(project.check_knowledge(self.args)["ok"])

    def test_init_preserves_constitution_and_identity(self):
        self.write(self.root, ".specify/memory/constitution.md", "Do not change this established constraint.\n")
        self.args.project_id = "different"
        with self.assertRaisesRegex(ValueError, "identity"):
            project.init_project(self.args)
        self.assertIn("Do not change", (self.root / ".specify/memory/constitution.md").read_text())

    def test_init_on_feature_branch_does_not_call_it_main(self):
        original = load(self.root / ".specify/project.yaml")["main_branch"]
        self.git(self.root, "checkout", "-qb", "feature/increment")
        (self.root / ".specify/project.yaml").unlink()
        project.init_project(self.args)
        self.assertEqual(load(self.root / ".specify/project.yaml")["main_branch"], original)

    def test_refresh_preserves_human_constraints_and_history(self):
        current = self.root / ".specify/knowledge/current.md"
        meta, body = read_record(current)
        write_record(current, meta, body + "\nHuman constraint: retain all v1 consumers.\nUnresolved: owner unknown.\n")
        self.write(self.root, "src/app.py", "VALUE = 2\n")
        self.assertFalse(project.check_knowledge(self.args)["ok"])
        project.refresh_knowledge(self.args)
        meta, body = read_record(current)
        self.assertIn("retain all v1 consumers", body)
        self.assertIn("owner unknown", body)
        self.assertEqual(body.count(project.AUTO_START), 1)
        self.assertTrue(list((self.root / ".specify/knowledge/history").glob("*.md")))
        self.assertTrue(project.check_knowledge(self.args)["ok"])

    def test_removed_boundary_candidates_remain_for_review(self):
        (self.root / "openapi.json").unlink()
        project.refresh_knowledge(self.args)
        index = load(self.root / ".specify/knowledge/boundaries/index.yaml")
        candidate = index["candidates"][0]
        self.assertEqual(candidate["observation_state"], "not_observed")
        self.assertTrue(candidate["review_required"])

    def test_context_detects_working_changes_and_tampering(self):
        self.assertTrue(project.build_context(self.args)["ok"])
        self.assertTrue(project.check_context(self.args)["ok"])
        self.write(self.root, "src/app.py", "VALUE = 2\n")
        self.assertFalse(project.check_context(self.args)["ok"])
        self.write(self.root, "src/app.py", "VALUE = 1\n")
        lock_path = self.root / "specs/feature/context-lock.json"
        lock = load(lock_path)
        lock["feature_id"] = "tampered"
        save(lock_path, lock)
        self.assertIn("context lock content was changed without rebuilding", project.check_context(self.args)["errors"])

    def test_context_build_requires_fresh_knowledge(self):
        self.write(self.root, "src/app.py", "VALUE = 3\n")
        self.assertFalse(project.build_context(self.args)["ok"])
        self.assertFalse((self.root / "specs/feature/context-lock.json").exists())

    def test_external_ref_requires_identity_and_digest(self):
        external = self.producer()
        self.set_inputs({"sources": [{"project_id": "producer", "path": "contract.md", "ref": "HEAD", "kind": "contract", "content_digest": "sha256:invalid"}]})
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            project.build_context(self.args)
        self.write(external, ".specify/project.yaml", json.dumps({"project_id": "wrong"}))
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            project.build_context(self.args)

    def test_external_unrelated_commit_keeps_context_valid(self):
        external = self.producer()
        self.set_inputs({"sources": [{"project_id": "producer", "path": "contract.md", "ref": "HEAD", "kind": "contract"}]})
        self.assertTrue(project.build_context(self.args)["ok"])
        self.write(external, "unrelated.txt", "Unrelated\n")
        self.commit(external)
        checked = project.check_context(self.args)
        self.assertTrue(checked["ok"], checked)
        self.assertTrue(checked["observations"])
        self.write(external, "contract.md", "# Contract\nChanged behavior\n")
        self.commit(external)
        self.assertFalse(project.check_context(self.args)["ok"])

    def test_design_target_requires_consumer_confirmation_reference(self):
        self.producer()
        self.set_inputs({"target_dependency_set": {"producer": {"release_id": "M11", "basis_kind": "design_confirmed", "basis_ref": {"project_id": "producer", "path": "contract.md", "ref": "HEAD", "kind": "design"}}}})
        with self.assertRaisesRegex(ValueError, "consumer.*confirmation"):
            project.build_context(self.args)

    def test_confirmed_design_is_pinned_not_implicitly_deployed(self):
        external = self.producer()
        self.git(external, "checkout", "-qb", "feature/future")
        self.write(external, "contract.md", "Future interface, not merged or deployed\n"); self.commit(external)
        decision = {"scope": "external_design", "accepted": True, "actor": "developer", "source": "explicit test decision", "reason": "adopt future interface", "artifact_digest": file_digest(external / "contract.md")}
        save(self.root / "external-decision.json", decision); self.commit(self.root)
        self.set_inputs({"target_dependency_set": {"producer": {"basis_kind": "confirmed_design", "basis_ref": {"project_id": "producer", "path": "contract.md", "ref": "feature/future", "kind": "design"}, "consumer_confirmation_ref": {"project_id": "consumer", "path": "external-decision.json", "ref": "HEAD", "kind": "decision"}}}})
        project.refresh_knowledge(self.args)
        self.assertTrue(project.build_context(self.args)["ok"])
        target = load(self.root / "specs/feature/context-lock.json")["target_dependency_set"]["producer"]
        self.assertEqual(target["availability"], "design_only_not_implemented_or_deployed")
        self.args.inputs = None
        self.assertTrue(project.build_context(self.args)["ok"])
        self.assertEqual(load(self.root / "specs/feature/context-lock.json")["target_dependency_set"]["producer"], target)

    def test_sensitive_and_symlink_paths_are_not_loaded(self):
        self.write(self.root, ".env", "PRIVATE_VALUE=do-not-read\n")
        (self.root / "linked.py").symlink_to(self.root / "src/app.py")
        inventory = project.inspect_project(self.args)["inventory"]
        self.assertNotIn(".env", [entry["path"] for entry in inventory["snapshot"]["files"]])
        self.assertTrue(any(item.get("path") == "linked.py" for item in inventory["snapshot"]["unknowns"]))
        self.args.feature_dir = "../outside"
        with self.assertRaises(ValueError):
            project.build_context(self.args)

    def test_register_exposes_actual_commands(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--root", default=str(self.root))
        project.register(parser.add_subparsers(dest="command", required=True))
        args = parser.parse_args(["context", "check", "--feature-dir", "specs/feature"])
        self.assertEqual(args.handler, project.check_context)
        args = parser.parse_args(["project", "inspect"])
        self.assertTrue(args.handler(args)["ok"])


if __name__ == "__main__":
    unittest.main()
