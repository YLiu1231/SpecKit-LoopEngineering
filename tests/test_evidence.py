import json
import sys
from helpers import RepoCase
from loop_runtime import evidence, project
from loop_runtime.common import load, save, file_digest


class EvidenceTests(RepoCase):
    def test_real_execution_and_final_input_drift(self):
        run = evidence.run_suite(self.root, self.feature)
        self.assertEqual(run["execution_state"], "complete")
        self.assertTrue(evidence.check(self.root, self.feature)["ok"])
        self.write("src/app.py", "VALUE = 9\n")
        self.assertFalse(evidence.check(self.root, self.feature)["ok"])
        run = evidence.run_suite(self.root, self.feature)
        self.assertEqual((run["execution_state"], run["evidence_verdict"]), ("complete", "fail"))

    def test_zero_exit_without_case_output_is_incomplete(self):
        self.write("tests/run.py", "pass\n")
        run = evidence.run_suite(self.root, self.feature)
        self.assertEqual(run["execution_state"], "incomplete")
        self.assertEqual(run["case_results"][0]["status"], "not_run")

    def test_skip_and_unregistered_cases_not_complete(self):
        self.write("tests/run.py", "import json,os\nopen(os.environ['LOOP_RESULT_FILE'],'w').write(json.dumps({'case_id':'ST-001','status':'skipped'}))\n")
        self.assertEqual(evidence.run_suite(self.root, self.feature)["execution_state"], "incomplete")

    def test_output_tampering_invalidates_evidence(self):
        run = evidence.run_suite(self.root, self.feature)
        self.write(run["commands"][0]["output_ref"], "changed\n")
        self.assertFalse(evidence.check(self.root, self.feature)["ok"])

    def test_junit_group_executes_once_and_checks_catalog(self):
        self.write("tests/run.py", "import os\nopen(os.environ['LOOP_RESULT_FILE'],'w').write('<testsuite><testcase classname=\"calc\" name=\"ok\"/><testcase classname=\"calc\" name=\"missing\"/></testsuite>')\n")
        p = self.root / ".specify/selftests/catalog.yaml"; cat = load(p)
        cat["runners"] = {"suite": {"command": [sys.executable, "tests/run.py"], "result_format": "junit"}}
        cat["cases"][0].update(runner_id="suite", native_id="calc::ok")
        save(p, cat)
        self.assertEqual(evidence.run_suite(self.root, self.feature)["execution_state"], "incomplete")
        cat["cases"].append({"id": "ST-002", "us_id": "US-001", "runner_id": "suite", "native_id": "calc::missing", "assertion": "second actual testcase"})
        save(p, cat)
        result = evidence.run_suite(self.root, self.feature)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["commands"]), 1)

    def test_synthetic_result_is_rejected(self):
        self.write("tests/run.py", "import json,os\nopen(os.environ['LOOP_RESULT_FILE'],'w').write(json.dumps({'example':True,'case_id':'ST-001','status':'pass','assertions':1}))\n")
        self.assertFalse(evidence.run_suite(self.root, self.feature)["ok"])

    def test_time_budget_prevents_new_execution(self):
        p = self.root / ".specify/project.yaml"; data = load(p); data["resource_budget"]["max_seconds"] = 0.01; save(p, data)
        self.write("tests/run.py", "import time\ntime.sleep(1)\n")
        run = evidence.run_suite(self.root, self.feature)
        self.assertEqual(run["execution_state"], "incomplete")
        with self.assertRaisesRegex(ValueError, "budget"):
            evidence.run_suite(self.root, self.feature)

    def test_plain_feature_note_does_not_invalidate_execution(self):
        evidence.run_suite(self.root, self.feature)
        self.write("specs/f/convergence.md", "Clarified report wording only.\n")
        self.assertTrue(evidence.check(self.root, self.feature)["ok"])

    def test_baseline_collects_failure_without_claiming_pass(self):
        self.write("src/app.py", "VALUE = 5\n")
        self.args.catalog = ".specify/selftests/catalog.yaml"
        result = project.baseline_project(self.args)
        self.assertTrue(result["ok"])
        self.assertEqual(result["baseline"]["evidence_verdict"], "fail")
        self.assertEqual(load(self.root / ".specify/knowledge/baseline.json")["execution_state"], "complete")

    def test_prompt_and_dependency_changes_invalidate_evidence(self):
        self.write("prompts/agent.md", "Run the actual assertion.")
        catpath = self.root / ".specify/selftests/catalog.yaml"; cat = load(catpath)
        cat["behavior_paths"].append("prompts"); save(catpath, cat)
        evidence.run_suite(self.root, self.feature)
        self.write("prompts/agent.md", "Changed agent behavior.")
        self.assertFalse(evidence.check(self.root, self.feature)["ok"])
        evidence.run_suite(self.root, self.feature)
        lock = load(self.feature / "context-lock.json"); lock["target_dependency_set"] = {"peer": {"version": "different"}}; save(self.feature / "context-lock.json", lock)
        self.assertFalse(evidence.check(self.root, self.feature)["ok"])

    def test_rewritten_summary_cannot_override_raw_case_results(self):
        self.write("src/app.py", "VALUE = 8\n")
        run = evidence.run_suite(self.root, self.feature)
        path = self.root / run["record_path"]; record = load(path)
        record["case_results"][0]["status"] = "pass"; record["evidence_verdict"] = "pass"; save(path, record)
        save(self.feature / "evidence/latest.json", {"path": run["record_path"], "digest": file_digest(path)})
        self.assertFalse(evidence.check(self.root, self.feature)["ok"])

    def test_missing_raw_case_is_not_filled_by_summary(self):
        run = evidence.run_suite(self.root, self.feature)
        path = self.root / run["record_path"]; record = load(path)
        original = self.root / record["commands"][0]["result_ref"]
        save(original, {"case_results": []})
        record["commands"][0]["result_digest"] = file_digest(original)
        save(path, record)
        save(self.feature / "evidence/latest.json", {"path": run["record_path"], "digest": file_digest(path)})
        checked = evidence.check(self.root, self.feature)
        self.assertFalse(checked["ok"])
        self.assertTrue(any("omit" in e for e in checked["errors"]))

    def test_missing_runner_is_not_filled_by_summary(self):
        catpath = self.root / ".specify/selftests/catalog.yaml"; cat = load(catpath)
        self.write("tests/second.py", "import os,json\nopen(os.environ['LOOP_RESULT_FILE'],'w').write(json.dumps({'case_id':'ST-002','status':'pass','assertions':1}))\n")
        cat["cases"].append({"id": "ST-002", "us_id": "US-001", "assertion": "second", "command": [sys.executable, "tests/second.py"]})
        save(catpath, cat); run = evidence.run_suite(self.root, self.feature)
        self.assertTrue(run["ok"])
        path = self.root / run["record_path"]; record = load(path); record["commands"].pop(); save(path, record)
        save(self.feature / "evidence/latest.json", {"path": run["record_path"], "digest": file_digest(path)})
        self.assertFalse(evidence.check(self.root, self.feature)["ok"])

    def test_catalog_edit_during_execution_invalidates_run(self):
        script = (self.root / "tests/run.py").read_text()
        script = "import json\np='.specify/selftests/catalog.yaml'\nc=json.load(open(p));c['environment']='changed-during-execution';open(p,'w').write(json.dumps(c))\n" + script
        self.write("tests/run.py", script)
        run = evidence.run_suite(self.root, self.feature)
        self.assertEqual(run["execution_state"], "incomplete")
        self.assertIn("Behavior inputs changed during execution", run["errors"])
