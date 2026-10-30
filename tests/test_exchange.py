import argparse
import copy
import shutil
from helpers import RepoCase
from loop_runtime import project, exchange, evidence
from loop_runtime.common import save, load, now, read_record, file_digest


class ExchangeTests(RepoCase):
    def setUp(self):
        super().setUp()
        self.peer = self.home / "b"; self.peer.mkdir()
        self.git(self.peer, "init", "-q", "-b", "main")
        self.write("README.md", "Consumer fixture", self.peer); self.commit(self.peer)
        project.init_project(argparse.Namespace(root=str(self.peer), project_id="b", main_branch="main"))
        for root in (self.root, self.peer):
            save(root / ".specify/local/workspace.json", {"projects": {"a": str(self.root), "b": str(self.peer)}})
        self.write("contracts/api.json", '{"field":"old"}\n')
        self.commit(self.root)

    def notice(self, revision=1, **changes):
        m = {"protocol_version": exchange.PROTOCOL, "record_type": "handoff", "producer_project": "a", "change_id": "a.feature",
             "revision": revision, "previous_revision": revision - 1 if revision > 1 else None,
             "feature_id": "f", "development_state": "design_confirmed", "baseline_release": "month-1", "target_release": "month-2",
             "design_ref": self.ref(self.root, "specs/f/plan.md"), "compatibility_ref": self.ref(self.root, "specs/f/compatibility.md"),
             "contract_changes": [{"contract_id": "a.api", "after": self.ref(self.root, "contracts/api.json", "contract"), "change_kind": "semantic"}],
             "required_consumers": [{"project_id": "b", "reason": "uses calculation", "basis": "confirmed boundary inventory"}],
             "unknown_dependencies": [], "evidence_refs": [], "origin_chain": [], "created_at": now(), "supersedes": [],
             "summary": "Calculation contract changes", "rationale": "Preserve old behavior while adding new option"}
        m.update(changes); return m

    def publish_notice(self, m=None):
        m = m or self.notice(); save(self.root / ".specify/local/input.json", m)
        result = exchange.publish(self.root, ".specify/local/input.json")
        self.commit(self.root)
        self.handoff = read_record(self.root / result["path"])[0]
        self.handoff_path = result["path"]
        return result

    def receipt(self, status="unaffected", **changes):
        decision = {"actor": "fixture-developer", "source": "explicit test fixture decision", "accepted": True, "reason": "reviewed inputs", "change_id": "a.feature"}
        save(self.peer / "decisions.json", {"decisions": [dict(decision, scope="external_design", artifact_digest=self.handoff["design_ref"]["content_digest"]), dict(decision, scope="impact"), dict(decision, scope="deferral")]})
        self.commit(self.peer)
        m = {"protocol_version": exchange.PROTOCOL, "record_type": "receipt", "producer_project": "a", "consumer_project": "b", "change_id": "a.feature",
             "receipt_id": "b.a-feature", "revision": 1, "handoff_revision": self.handoff["revision"], "handoff_ref": self.ref(self.root, self.handoff_path, "handoff"),
             "contract_assumptions": [{"contract_id": "a.api", "content_digest": self.handoff["contract_changes"][0]["after"]["content_digest"]}],
             "target_dependency_set": {"a": {"basis_kind": "confirmed_design", "basis_ref": self.handoff["design_ref"]}},
             "status": status, "recheck_required": False, "affected_features": [], "evidence_refs": [], "decision_refs": [self.ref(self.peer, "decisions.json", "decision")],
             "source_refs": [self.ref(self.peer, "README.md", "code")], "reason": "consumer reviewed contract", "observed_at": now()}
        if status == "verified":
            m["feature_id"] = "f"
        m.update(changes); return m

    def publish_receipt(self, m):
        save(self.peer / ".specify/local/receipt.json", m)
        return exchange.publish(self.peer, ".specify/local/receipt.json", expected_type="receipt")

    def test_producer_cannot_replace_consumer_assessment(self):
        self.publish_notice()
        before = exchange.closure(self.root, "a.feature")
        self.assertFalse(before["joint_compatibility_ready"])
        self.assertEqual(before["consumers"][0]["status"], "not_assessed")
        self.publish_receipt(self.receipt())
        after = exchange.closure(self.root, "a.feature")
        self.assertTrue(after["assessment_resolved"])
        self.assertTrue(after["joint_compatibility_ready"])
        self.assertFalse(after["release_authorized"])
        self.assertFalse(exchange.scan(self.peer)["changes"][0]["recheck_required"])

    def test_deferral_resolves_disposition_without_joint_readiness(self):
        self.publish_notice()
        self.publish_receipt(self.receipt("deferred", deferral={"accepted": True, "target_release": "month-3", "scope": "new option", "reason": "preserve old behavior for now"}))
        r = exchange.closure(self.root, "a.feature")
        self.assertTrue(r["assessment_resolved"]); self.assertFalse(r["joint_compatibility_ready"])
        self.assertTrue(r["has_accepted_deferral"])

    def test_related_change_and_withdrawal_invalidate_receipt(self):
        self.publish_notice(); self.publish_receipt(self.receipt())
        self.write("contracts/api.json", '{"field":"different semantic"}\n'); self.commit(self.root)
        self.publish_notice(self.notice(2))
        self.assertFalse(exchange.closure(self.root, "a.feature")["joint_compatibility_ready"])
        self.assertTrue(exchange.scan(self.peer)["changes"][0]["recheck_required"])
        self.publish_notice(self.notice(3, development_state="withdrawn"))
        self.assertFalse(exchange.closure(self.root, "a.feature")["assessment_resolved"])

    def test_unrelated_commits_do_not_invalidate_fixed_receipt(self):
        self.publish_notice(); self.publish_receipt(self.receipt())
        self.write("unrelated.txt", "documentation only"); self.commit(self.root)
        self.assertTrue(exchange.closure(self.root, "a.feature")["joint_compatibility_ready"])

    def test_conflicting_parallel_contracts_are_visible(self):
        self.publish_notice(); self.publish_receipt(self.receipt())
        self.write("contracts/api.json", '{"field":"parallel conflicting semantic"}\n'); self.commit(self.root)
        self.publish_notice(self.notice(change_id="a.parallel"))
        r = exchange.closure(self.root, "a.feature")
        self.assertFalse(r["joint_compatibility_ready"]); self.assertTrue(r["contract_conflicts"])

    def test_false_decision_wrong_hash_and_foreign_write_rejected(self):
        self.publish_notice(); r = self.receipt()
        save(self.peer / "decisions.json", {"decisions": []}); self.commit(self.peer)
        r["decision_refs"] = [self.ref(self.peer, "decisions.json", "decision")]
        with self.assertRaisesRegex(ValueError, "consumer confirmation"):
            self.publish_receipt(r)
        r = self.receipt(); r["contract_assumptions"][0]["content_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.publish_receipt(r)
        save(self.peer / ".specify/local/input.json", self.notice())
        with self.assertRaisesRegex(ValueError, "own-project"):
            exchange.publish(self.peer, ".specify/local/input.json")

    def test_no_change_handoff_is_immutable_and_idempotent(self):
        result = self.publish_notice(self.notice(contract_changes=[], required_consumers=[], no_external_change_reason="internal refactor"))
        replay = exchange.publish(self.root, ".specify/local/input.json")
        self.assertTrue(replay["idempotent"])
        m = load(self.root / ".specify/local/input.json"); m["summary"] = "different"
        save(self.root / ".specify/local/input.json", m)
        with self.assertRaisesRegex(ValueError, "already exists"):
            exchange.publish(self.root, ".specify/local/input.json")

    def test_index_invalid_input_does_not_partially_publish(self):
        save(self.root / ".specify/local/input.json", self.notice())
        save(self.root / exchange.INDEX, {"project_id": "wrong"})
        with self.assertRaises(ValueError):
            exchange.publish(self.root, ".specify/local/input.json")
        self.assertFalse((self.root / ".specify/exchange/outbox/a.feature/r1.md").exists())

    def test_verified_receipt_requires_actual_complete_cases(self):
        self.publish_notice()
        for name in ("src", "tests", "specs"):
            shutil.copytree(self.root / name, self.peer / name)
        save(self.peer / ".specify/selftests/catalog.yaml", load(self.root / ".specify/selftests/catalog.yaml"))
        cfg = load(self.peer / ".specify/project.yaml"); cfg["resource_budget"] = {"max_seconds": 60}; save(self.peer / ".specify/project.yaml", cfg)
        save(self.peer / "specs/f/context-lock.json", {"target_dependency_set": {"a": {"basis_kind": "confirmed_design", "basis_ref": self.handoff["design_ref"]}}})
        run = evidence.run_suite(self.peer, "specs/f")
        self.assertTrue(run["ok"])
        run["record_path"] = evidence.export(self.peer, "specs/f")["path"]
        self.commit(self.peer)
        r = self.receipt("verified", evidence_refs=[self.ref(self.peer, run["record_path"], "evidence")])
        self.publish_receipt(r)
        self.assertTrue(exchange.closure(self.root, "a.feature")["joint_compatibility_ready"])
        stored = load(self.peer / run["record_path"]); stored["example"] = True; save(self.peer / run["record_path"], stored); self.commit(self.peer)
        r["revision"] = 2; r["evidence_refs"] = [self.ref(self.peer, run["record_path"], "evidence")]
        with self.assertRaisesRegex(ValueError, "synthetic"):
            self.publish_receipt(r)

    def release(self, record_id, previous=None, action="publish"):
        cfg = load(self.root / ".specify/project.yaml")
        cfg["release_authority"] = {"production": {"project_id": "a", "path": "release-current.json", "ref": "main"}}
        save(self.root / ".specify/project.yaml", cfg)
        fact = {"record_id": record_id, "project_id": "a", "environment": "production", "release_id": "month-1" if action == "rollback" else "month-2",
                "commit": self.git(self.root, "rev-parse", "HEAD"), "action": action, "previous_record_id": previous, "occurred_at": now()}
        save(self.root / "release-current.json", fact); self.commit(self.root)
        entry = dict(fact, source_ref=self.ref(self.root, "release-current.json", "release_record"))
        exchange.record_release(self.root, entry)
        return entry

    def test_authority_rollback_invalidates_assumption_and_preserves_history(self):
        first = self.release("release-1")
        self.assertTrue(exchange.record_release(self.root, first)["current_confirmed"])
        self.publish_notice(); self.publish_receipt(self.receipt(release_assumptions=[{"project_id": "a", "environment": "production", "record_id": "release-1"}]))
        self.assertTrue(exchange.closure(self.root, "a.feature")["joint_compatibility_ready"])
        self.release("release-2", "release-1", "rollback")
        status = exchange.release_status(self.root, "production")
        self.assertEqual(status["history_count"], 2); self.assertEqual(status["current"]["action"], "rollback")
        self.assertFalse(exchange.closure(self.root, "a.feature")["joint_compatibility_ready"])
        self.assertFalse(exchange.scan(self.peer)["ok"])

    def test_unimported_authority_is_unknown_not_last_historical_release(self):
        self.release("release-1")
        fact = load(self.root / "release-current.json"); fact["record_id"] = "not-imported"
        save(self.root / "release-current.json", fact); self.commit(self.root)
        self.assertFalse(exchange.release_status(self.root, "production")["current_confirmed"])

    def test_reference_cannot_cross_or_read_sensitive_material(self):
        for path in ("../outside", ".env", ".git/config", ".aws/credentials", "secrets.yaml"):
            with self.assertRaises(ValueError):
                exchange._path(self.root, path)
        (self.root / "link.txt").symlink_to(self.peer / "README.md")
        with self.assertRaisesRegex(ValueError, "symlink"):
            exchange._path(self.root, "link.txt")

    def test_context_target_change_reopens_receipt_and_scopes_closure(self):
        self.publish_notice()
        r = self.receipt(feature_id="f")
        save(self.peer / "specs/f/context-lock.json", {"target_dependency_set": r["target_dependency_set"]})
        self.publish_receipt(r)
        self.assertTrue(exchange.closure(self.root, "a.feature")["joint_compatibility_ready"])
        changed = copy.deepcopy(r["target_dependency_set"]); changed["a"]["release_id"] = "month-3"
        context = {"target_dependency_set": changed}
        save(self.peer / "specs/f/context-lock.json", context)
        scan = exchange.scan(self.peer, context)
        self.assertTrue(scan["changes"][0]["recheck_required"])
        self.assertIn("target dependency", scan["changes"][0]["reason"])
        self.assertFalse(exchange.closure(self.root, "a.feature")["joint_compatibility_ready"])

    def test_key_node_context_detects_new_notice_without_moving_selected_ref(self):
        args = argparse.Namespace(root=str(self.peer), feature_dir="specs/f", inputs=None)
        (self.peer / "specs/f").mkdir(parents=True)
        project.refresh_knowledge(args); project.build_context(args)
        self.assertTrue(project.check_context(args)["ok"])
        self.publish_notice()
        checked = project.check_context(args)
        self.assertFalse(checked["ok"])
        self.assertTrue(any("external notices" in e for e in checked["errors"]))
        project.refresh_knowledge(args); project.build_context(args)
        self.assertTrue(project.check_context(args)["ok"])
        self.write("unrelated.txt", "no contract change"); self.commit(self.root)
        self.assertTrue(project.check_context(args)["ok"])

    def test_forked_release_history_is_rejected_and_never_confirmed(self):
        self.release("r1"); self.release("r2", "r1")
        with self.assertRaisesRegex(ValueError, "history tip"):
            self.release("r3", "r1", "rollback")
        self.assertFalse(exchange.release_status(self.root, "production")["current_confirmed"])
        fact = load(self.root / "release-current.json")
        save(self.root / ".specify/exchange/releases/production/r3.json", dict(fact, source_ref=self.ref(self.root, "release-current.json", "release_record")))
        status = exchange.release_status(self.root, "production")
        self.assertFalse(status["current_confirmed"])
        self.assertTrue(any("forks" in e["reason"] for e in status["errors"]))

    def test_shared_failed_raw_result_cannot_be_relabelled_pass(self):
        self.publish_notice()
        for name in ("src", "tests", "specs"):
            shutil.copytree(self.root / name, self.peer / name)
        save(self.peer / ".specify/selftests/catalog.yaml", load(self.root / ".specify/selftests/catalog.yaml"))
        cfg = load(self.peer / ".specify/project.yaml"); cfg["resource_budget"] = {"max_seconds": 60}; save(self.peer / ".specify/project.yaml", cfg)
        save(self.peer / "specs/f/context-lock.json", {"target_dependency_set": {"a": {"basis_kind": "confirmed_design", "basis_ref": self.handoff["design_ref"]}}})
        self.write("src/app.py", "VALUE = 9\n", self.peer)
        run = evidence.run_suite(self.peer, "specs/f"); self.assertEqual(run["evidence_verdict"], "fail")
        exported = evidence.export(self.peer, "specs/f")["path"]
        record = load(self.peer / exported); record["case_results"][0]["status"] = "pass"; record["evidence_verdict"] = "pass"
        save(self.peer / exported, record); self.commit(self.peer)
        r = self.receipt("verified", evidence_refs=[self.ref(self.peer, exported, "evidence")])
        with self.assertRaisesRegex(ValueError, "shared execution evidence invalid"):
            self.publish_receipt(r)
