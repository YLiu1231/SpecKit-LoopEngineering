import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from loop_runtime import project
from loop_runtime.common import save, load, file_digest


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name).resolve()
        self.root = self.home / "a"
        self.root.mkdir()
        self.git(self.root, "init", "-q", "-b", "main")
        self.write("src/app.py", "VALUE = 2\n")
        self.commit(self.root)
        self.args = argparse.Namespace(root=str(self.root), project_id="a", main_branch="main", feature_dir="specs/f", inputs=None)
        project.init_project(self.args)
        self.feature = self.root / "specs/f"
        self.feature.mkdir(parents=True)
        self.write("specs/f/spec.md", "# User Stories\nUS-001: preserve calculation\nFR-001: returns 2\nSC-001: assertions pass\n")
        for name, text in {"plan.md": "Local calculation, preserve the existing interface.", "tasks.md": "- [ ] T001 implement US-001", "us-design.md": "US-001 checks VALUE with ST-001", "compatibility.md": "No external behavior changes."}.items():
            self.write("specs/f/" + name, text)
        self.write("tests/run.py", "import json, os, runpy\nv=runpy.run_path('src/app.py')['VALUE']\nr={'case_id':'ST-001','status':'pass' if v==2 else 'fail','assertions':1}\nopen(os.environ['LOOP_RESULT_FILE'],'w').write(json.dumps(r))\nraise SystemExit(0 if v==2 else 1)\n")
        save(self.root / ".specify/selftests/catalog.yaml", {"cases": [{"id": "ST-001", "us_id": "US-001", "command": [sys.executable, "tests/run.py"], "assertion": "VALUE equals 2"}], "behavior_paths": ["src", "tests"]})
        save(self.feature / "traceability.json", {"requirements": ["FR-001"], "stories": [{"id": "US-001", "requirements": ["FR-001"], "tasks": ["T001"], "cases": ["ST-001"]}]})
        from loop_runtime.compatibility import CATEGORIES
        save(self.feature / "boundary-review.json", {"categories": {key: {"status": "not_applicable", "reason": "isolated calculation fixture"} for key in CATEGORIES}, "unknowns": []})
        save(self.feature / "compatibility.json", {"interactions": [], "no_external_change_reason": "isolated calculation fixture"})
        c = load(self.root / ".specify/project.yaml"); c["resource_budget"] = {"max_seconds": 60}; save(self.root / ".specify/project.yaml", c)
        self.refresh()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text, root=None):
        p = (root or self.root) / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text, encoding="utf-8"); return p

    @staticmethod
    def git(root, *args):
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout.strip()

    def commit(self, root):
        self.git(root, "add", ".")
        self.git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")
        return self.git(root, "rev-parse", "HEAD")

    def refresh(self):
        project.refresh_knowledge(self.args)
        return project.build_context(self.args)

    def approve(self, phase):
        from loop_runtime.gate import binding
        path = self.feature / "decisions.json"; data = load(path, {"decisions": []})
        data["decisions"] = [d for d in data["decisions"] if d["scope"] != phase]
        data["decisions"].append({"id": "approve-" + phase, "scope": phase, "actor": "fixture-developer", "source": "test-case-explicit-decision", "reason": "reviewed the fixture artifacts", "accepted": True, "artifact_digest": binding(self.root, self.feature, phase)["artifact_digest"], "unresolved_material_questions": []})
        save(path, data)

    def ref(self, root, path, kind="design"):
        return {"project_id": load(root / ".specify/project.yaml")["project_id"], "path": path, "ref": self.git(root, "rev-parse", "HEAD"), "content_digest": file_digest(root / path), "kind": kind}
