---
name: "loop-design"
description: "Run a bounded Spec Kit design loop: plan, task decomposition, cross-artifact analysis, remediation, and architecture gate."
argument-hint: "Optional design constraints or areas that need special attention"
compatibility: "Requires an active feature with a passing requirements loop"
user-invocable: true
disable-model-invocation: false
---

# Design Loop

Transform approved intent into a feasible, traceable, independently testable plan.

## Contract

- Generator: `speckit-plan` and `speckit-tasks`.
- Evaluators: `speckit-analyze`, architecture fitness checks, and
  `.specify/scripts/loopctl.py check design --record`.
- Budget: read `loops.design` from `.specify/loop-engineering/policy.json`.
- The evaluator pass is read-only. The generator may revise only after findings are
  recorded.
- Human gate: one grouped decision only for architecture, new dependencies,
  external integrations, persistence/schema migrations, security boundaries, or a
  meaningful cost/operability tradeoff.

## Loop

1. Confirm the requirements loop is `PASS` in `loop-state.json`. Otherwise return to
   `loop-requirements`; do not design against unstable intent.
2. Invoke `speckit-plan`, then `speckit-tasks`. Organize tasks as vertical,
   independently verifiable slices. Every task must name its file/area and completion
   evidence; tests precede implementation where behavior changes.
3. Invoke `speckit-analyze` as a read-only critic. Add two explicit fitness passes:
   - structural: dependency direction, boundary ownership, forbidden coupling,
     migration/rollback, observability;
   - semantic: every FR, SC, acceptance scenario, and constitution MUST has a buildable
     task or an explicit non-buildable rationale.
4. Save a compact evaluator artifact to the active feature's `analysis.md`. It must
   contain finding IDs, severity, source reference, evidence, remediation, and end with
   exactly `Gate-Result: PASS` only when no CRITICAL/HIGH finding remains and all
   traceability checks pass. Otherwise end with `Gate-Result: FAIL`.
5. Feed findings back to `speckit-plan` or `speckit-tasks` according to ownership.
   Do not patch the spec to make an inconvenient finding disappear.
6. Run:

   `.specify/scripts/run-python.sh .specify/scripts/loopctl.py check design --record`

7. On `continue`, remediate only failed checks. On `escalate-*`, stop with alternatives
   and tradeoffs. On `stop-pass`, request the single architecture/execution gate.

## Exit Evidence

Report task count, requirements-to-task coverage, fitness checks, finding counts by
severity, deterministic score, selected tradeoffs, and rollback strategy.
