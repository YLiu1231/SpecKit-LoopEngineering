from helpers import RepoCase
from loop_runtime import gate, evidence, project, compatibility, exchange
from loop_runtime.common import save, load, digest, write_record, now


class GateTests(RepoCase):
    def ready(self):
        self.refresh(); self.approve("requirements"); self.approve("design")

    def complete_tasks(self):
        self.write("specs/f/tasks.md", "- [x] T001 implement US-001")

    def finish_with_git_handoff(self, run, implementation=None, state="implemented"):
        meta = {"protocol_version": exchange.PROTOCOL, "record_type": "handoff", "producer_project": "a", "change_id": "a.f", "feature_id": "f", "revision": 1, "previous_revision": None,
                "development_state": state, "baseline_release": "unknown", "target_release": "month-2", "design_ref": self.ref(self.root, "specs/f/plan.md"), "compatibility_ref": self.ref(self.root, "specs/f/compatibility.md"),
                "implementation_ref": implementation, "contract_changes": [], "no_external_change_reason": "internal only", "required_consumers": [], "unknown_dependencies": [], "evidence_refs": [], "origin_chain": [], "supersedes": [], "created_at": now(), "summary": "Preserve existing result", "rationale": "validated fixture behavior"}
        save(self.root / ".specify/local/handoff.json", meta); exchange.publish(self.root, ".specify/local/handoff.json")
        write_record(self.root / ".specify/knowledge/features/f.md", {"feature_id": "f", "input_digest": run["input_snapshot"]["code_digest"]}, "Actual execution: " + run["record_path"])
        self.refresh()
        return gate.evaluate(self.root, self.feature, "convergence")

    def test_design_only_handoff_cannot_finish_convergence(self):
        self.commit(self.root); self.ready(); self.complete_tasks()
        run = evidence.run_suite(self.root, self.feature)
        r = self.finish_with_git_handoff(run, state="design_confirmed")
        self.assertFalse(r["ok"])
        self.assertTrue(any("must describe implemented code" in e for e in r["errors"]))

    def test_git_handoff_must_match_deleted_inputs_too(self):
        self.write("src/obsolete.py", "unused_but_behavioral = True\n"); self.commit(self.root)
        old = self.ref(self.root, "src/app.py", "code")
        (self.root / "src/obsolete.py").unlink()
        self.ready(); self.complete_tasks(); run = evidence.run_suite(self.root, self.feature)
        r = self.finish_with_git_handoff(run, old)
        self.assertFalse(r["ok"])
        self.assertTrue(any("exact tested behavior inputs" in e for e in r["errors"]))

    def test_git_handoff_matches_the_tested_commit(self):
        self.commit(self.root); self.ready(); self.complete_tasks()
        run = evidence.run_suite(self.root, self.feature)
        r = self.finish_with_git_handoff(run, self.ref(self.root, "src/app.py", "code"))
        self.assertTrue(r["ok"], r)

    def test_real_full_four_loop_path(self):
        self.commit(self.root); self.ready()
        self.assertTrue(gate.evaluate(self.root, self.feature, "requirements")["ok"])
        self.assertTrue(gate.evaluate(self.root, self.feature, "design")["ok"])
        self.complete_tasks(); run = evidence.run_suite(self.root, self.feature)
        r = gate.evaluate(self.root, self.feature, "implementation", True)
        self.assertTrue(r["ok"], r)
        meta = {"protocol_version": exchange.PROTOCOL, "record_type": "handoff", "producer_project": "a", "change_id": "a.f", "feature_id": "f", "revision": 1, "previous_revision": None,
                "development_state": "implemented", "baseline_release": "unknown", "target_release": "month-2", "design_ref": self.ref(self.root, "specs/f/plan.md"), "compatibility_ref": self.ref(self.root, "specs/f/compatibility.md"),
                "implementation_ref": {"kind": "code", "project_id": "a", "storage": "local_snapshot", "visibility": "local_only", "snapshot_id": run["run_id"], "base_commit": run["input_snapshot"]["base_commit"], "input_digest": run["input_snapshot"]["code_digest"]},
                "source_available_to_consumers": False, "contract_changes": [], "no_external_change_reason": "internal only", "required_consumers": [], "unknown_dependencies": [], "evidence_refs": [], "origin_chain": [], "supersedes": [], "created_at": now(), "summary": "Calculation preserved", "rationale": "existing result stays 2"}
        save(self.root / ".specify/local/handoff.json", meta); exchange.publish(self.root, ".specify/local/handoff.json")
        write_record(self.root / ".specify/knowledge/features/f.md", {"feature_id": "f", "input_digest": run["input_snapshot"]["code_digest"]}, "Preserved calculation; rationale and constraints recorded in plan. Actual evidence: " + run["record_path"])
        self.refresh()
        r = gate.evaluate(self.root, self.feature, "convergence", True)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["gate_decision"], "pass")

    def test_fail_can_be_accepted_without_rewriting_evidence(self):
        self.ready(); self.complete_tasks(); self.write("src/app.py", "VALUE = 3\n")
        evidence.run_suite(self.root, self.feature)
        self.assertFalse(gate.evaluate(self.root, self.feature, "implementation")["ok"])
        finding = {"id": "F-1", "severity": "medium", "description": "known mismatch", "case_ids": ["ST-001"]}
        save(self.feature / "findings.json", {"findings": [finding]})
        ds = load(self.feature / "decisions.json")
        ds["decisions"].append({"id": "risk-1", "scope": "risk", "artifact_digest": gate.finding_digest(finding), "accepted": True, "actor": "developer", "source": "explicit fixture acceptance", "reason": "defer known mismatch", "unresolved_material_questions": []})
        save(self.feature / "decisions.json", ds)
        r = gate.evaluate(self.root, self.feature, "implementation")
        self.assertTrue(r["ok"], r); self.assertEqual(r["gate_decision"], "conditional_pass")
        self.assertEqual(r["execution_state"], "complete"); self.assertEqual(r["evidence_verdict"], "fail")

    def test_incomplete_cannot_be_accepted_as_risk(self):
        self.ready(); self.complete_tasks()
        self.write("tests/run.py", "pass\n"); evidence.run_suite(self.root, self.feature)
        r = gate.evaluate(self.root, self.feature, "implementation")
        self.assertFalse(r["ok"]); self.assertEqual(r["execution_state"], "incomplete")

    def test_changed_design_requires_new_content_bound_decision(self):
        self.ready(); self.write("specs/f/plan.md", "Different architecture")
        self.refresh()
        r = gate.evaluate(self.root, self.feature, "design")
        self.assertFalse(r["ok"]); self.assertTrue(any("Current design" in e for e in r["errors"]))

    def test_removed_us_mapping_and_missing_boundary_category_hold(self):
        self.ready()
        save(self.feature / "traceability.json", {"requirements": ["FR-001"], "stories": []})
        review = load(self.feature / "boundary-review.json"); del review["categories"]["timing"]; save(self.feature / "boundary-review.json", review)
        self.refresh(); self.approve("design")
        r = gate.evaluate(self.root, self.feature, "design")
        self.assertFalse(r["ok"]); self.assertTrue(any("timing" in e for e in r["errors"]))

    def test_another_story_sharing_fr_cannot_disappear_from_traceability(self):
        self.write("specs/f/spec.md", (self.feature / "spec.md").read_text() + "US-002: same FR with a second user journey\n")
        self.ready()
        r = gate.evaluate(self.root, self.feature, "design")
        self.assertFalse(r["ok"])
        self.assertTrue(any("every specified US" in e for e in r["errors"]))

    def test_resolved_finding_requires_current_evidence(self):
        self.ready()
        finding = {"id": "F-1", "severity": "high", "description": "architecture conflict", "disposition": "resolved"}
        save(self.feature / "findings.json", {"findings": [finding]})
        self.assertFalse(gate.evaluate(self.root, self.feature, "design")["ok"])
        from loop_runtime.common import file_digest
        finding.update(resolution_reason="reviewed corrected design", resolution_evidence=[{"path": "specs/f/plan.md", "digest": file_digest(self.feature / "plan.md")}])
        save(self.feature / "findings.json", {"findings": [finding]})
        self.assertTrue(gate.evaluate(self.root, self.feature, "design")["ok"])

    def test_four_combinations_and_rollback_exception(self):
        cat = load(self.root / ".specify/selftests/catalog.yaml")
        rows = {}; versions = {"local": {"old": "a1", "new": "a2"}, "peer": {"old": "b1", "new": "b2"}}
        for i, key in enumerate(compatibility.COMBINATIONS):
            cid = "ST-" + str(i + 2); a, b = key.split("_")
            cat["cases"].append({"id": cid, "us_id": "US-001", "assertion": "preserves old business", "compatibility_combination": key, "peer_project": "b", "versions": {"local": versions["local"][a], "peer": versions["peer"][b]}})
            rows[key] = {"expected_behavior": "preserve business", "case_ids": [cid], "new_capability_degradation": "explicitly unavailable on old peer"}
        save(self.root / ".specify/selftests/catalog.yaml", cat)
        recovery = {"stateful_effects": "new message format", "independent_rollback_supported": False, "alternative": "disable capability then jointly restore", "limitations": "not drilled yet", "case_ids": []}
        pair = {"peer_project": "b", "contract_ids": ["b.api"], "support_window": "a1/a2 with b1/b2 during month-2", "local_versions": versions["local"], "peer_versions": versions["peer"], "combinations": rows, "recovery": recovery}
        save(self.feature / "compatibility.json", {"interactions": [pair]})
        lock = load(self.feature / "context-lock.json"); lock["target_dependency_set"] = {"b": {"basis_kind": "implementation"}}; save(self.feature / "context-lock.json", lock)
        self.assertFalse(compatibility.evaluate(self.root, self.feature, [])["ok"])
        records = [{"scope": scope, "accepted": True, "artifact_digest": digest(recovery), "actor": "developer", "source": "fixture confirmation", "reason": "bounded recovery exception", "unresolved_material_questions": []} for scope in ("recovery_exception", "recovery_unverified")]
        r = compatibility.evaluate(self.root, self.feature, records)
        self.assertTrue(r["ok"], r); self.assertTrue(r["warnings"])
        del pair["combinations"]["new_old"]; save(self.feature / "compatibility.json", {"interactions": [pair]})
        self.assertFalse(compatibility.evaluate(self.root, self.feature, records)["ok"])

    def test_four_version_combinations_execute_real_adapter_assertions(self):
        import sys
        self.write("src/producer_old.py", "def response():\n    return {'amount': 10}\n")
        self.write("src/producer_new.py", "def response():\n    return {'amount': 10, 'currency': 'EUR'}\n")
        self.write("src/consumer_old.py", "def read(value):\n    return value['amount'], None\n")
        self.write("src/consumer_new.py", "def read(value):\n    return value['amount'], value.get('currency', 'USD')\n")
        self.write("tests/matrix.py", """import json, os, runpy
rows = []
for a, b in [('old','old'),('new','old'),('old','new'),('new','new')]:
    status = 'pass'
    try:
        response = runpy.run_path('src/producer_' + a + '.py')['response']()
        actual = runpy.run_path('src/consumer_' + b + '.py')['read'](response)
        expected = (10, None if b == 'old' else 'EUR' if a == 'new' else 'USD')
        assert actual == expected, (actual, expected)
    except (AssertionError, KeyError):
        status = 'fail'
    rows.append({'case_id': a + '_' + b, 'status': status, 'assertions': 1})
open(os.environ['LOOP_RESULT_FILE'], 'w').write(json.dumps({'case_results': rows}))
raise SystemExit(0 if all(r['status'] == 'pass' for r in rows) else 1)
""")
        cat = load(self.root / ".specify/selftests/catalog.yaml")
        cat["runners"] = {"matrix": {"command": [sys.executable, "tests/matrix.py"], "result_format": "case-json"}}
        cat["cases"] += [{"id": key, "us_id": "US-001", "runner_id": "matrix", "assertion": "preserve amount and explicitly degrade currency on old producer", "peer_project": "b", "compatibility_combination": key} for key in compatibility.COMBINATIONS]
        save(self.root / ".specify/selftests/catalog.yaml", cat)
        run = evidence.run_suite(self.root, self.feature)
        self.assertTrue(run["ok"]); self.assertEqual(len(run["case_results"]), 5)
        self.write("src/producer_new.py", "def response():\n    return {'total': 10, 'currency': 'EUR'}\n")
        self.assertFalse(evidence.check(self.root, self.feature)["ok"])
        run = evidence.run_suite(self.root, self.feature)
        self.assertEqual(run["execution_state"], "complete")
        self.assertEqual({r["case_id"] for r in run["case_results"] if r["status"] == "fail"}, {"new_old", "new_new"})
