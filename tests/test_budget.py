from helpers import RepoCase
from loop_runtime import budget
from loop_runtime.common import file_digest


class BudgetTests(RepoCase):
    def attempt(self, number, loop="implementation", progress=False):
        p = self.write("specs/f/diagnosis.txt", "attempt " + str(number))
        return {"problem_id": "BUG-1", "attempt_id": "try-" + str(number), "loop": loop,
                "hypothesis": "check missing dependency", "evidence_refs": [{"path": str(p.relative_to(self.root)), "digest": file_digest(p)}],
                "progress": progress, "progress_reason": "new reproducible evidence" if progress else "", "elapsed_seconds": 0.1}

    def test_cross_loop_stagnation_and_explicit_continuation(self):
        budget.record(self.root, self.feature, self.attempt(1))
        r = budget.record(self.root, self.feature, self.attempt(2, "design"))
        self.assertEqual(r["problems"]["BUG-1"]["action"], "escalate")
        with self.assertRaises(ValueError):
            budget.record(self.root, self.feature, self.attempt(3))
        budget.resume(self.root, self.feature, {"id": "resume-1", "actor": "developer", "source": "fixture decision", "reason": "new cause identified", "accepted": True, "problem_id": "BUG-1", "extra_attempts": 1})
        r = budget.record(self.root, self.feature, self.attempt(3, progress=True))
        self.assertEqual(r["problems"]["BUG-1"]["attempts"], 3)
        self.assertEqual(r["problems"]["BUG-1"]["action"], "continue")

    def test_attempt_replay_is_idempotent_not_a_reset(self):
        a = self.attempt(1, progress=True)
        budget.record(self.root, self.feature, a)
        budget.record(self.root, self.feature, a)
        self.assertEqual(budget.report(self.root, self.feature)["problems"]["BUG-1"]["attempts"], 1)
        a["hypothesis"] = "different"
        with self.assertRaises(ValueError):
            budget.record(self.root, self.feature, a)

    def test_fake_progress_without_evidence_rejected(self):
        a = self.attempt(1, progress=True); a["evidence_refs"] = []
        with self.assertRaises(ValueError):
            budget.record(self.root, self.feature, a)

    def test_problem_budget_is_not_shared_by_independent_us(self):
        for i in range(6):
            a = self.attempt(i, progress=True); a["problem_id"] = "BUG-" + str(i)
            budget.record(self.root, self.feature, a)
        self.assertEqual(len(budget.report(self.root, self.feature)["problems"]), 6)

    def test_example_attempt_cannot_become_real_usage(self):
        entry = self.attempt(1); entry["example"] = True
        with self.assertRaisesRegex(ValueError, "Example attempts"):
            budget.record(self.root, self.feature, entry)
