---
name: "loop-implementation"
description: "Run a bounded evidence-driven implementation loop over one small task or story slice using red-green-refactor, tests, and diff review."
argument-hint: "Optional task ID or story slice; otherwise choose the smallest unblocked slice"
compatibility: "Requires an active feature with a passing design loop"
user-invocable: true
disable-model-invocation: false
---

# Implementation Loop

Complete one independently testable slice at a time. Small batches keep feedback
fast and make failures attributable.

## Contract

- Generator: application code and tests for one task/story slice.
- Evaluators, cheapest first: reproduction/targeted test, type/lint/static checks,
  changed-scope suite, full relevant suite, diff/semantic review.
- Budget: at most `loops.implementation.max_iterations` attempts per failing slice.
- Ground truth comes from tool output, not model confidence.
- Human gate: only when evidence invalidates the approved spec/plan, requires a new
  dependency or migration, or crosses the project/network/deployment boundary.

## Loop

1. Confirm requirements and design states are `PASS`. Select the smallest unblocked
   unchecked task, or the task ID in `$ARGUMENTS`. State its acceptance evidence.
2. Establish a baseline. For a bug, reproduce it. For new behavior, create a failing
   test or executable acceptance check. Preserve the red result as evidence.
3. Implement the minimum change that makes the check pass. Do not refactor unrelated
   code or complete adjacent tasks.
4. Evaluate in this order and stop at the first failure:
   targeted test -> type/lint/static analysis -> changed-scope tests -> relevant suite.
5. Review the diff against the selected task, spec references, security boundaries,
   failure behavior, and rollback. The authoring pass cannot silently waive a finding.
6. If an evaluator fails, classify the failure as implementation defect, test defect,
   design defect, environment defect, or flaky signal. Fix only the owning layer and
   repeat. If the score stagnates, stop and escalate; never "try harder" without new
   evidence.
7. Mark the task complete only after the evidence passes. Append or update the active
   feature's `evidence/implementation.json` using this shape:

   ```json
   {
     "commands": [
       {
         "command": "exact command",
         "scope": "targeted|static|changed-scope|suite",
         "exit_code": 0,
         "timestamp": "ISO-8601"
       }
     ],
     "review": {
       "task": "T001",
       "result": "PASS",
       "residual_risks": []
     }
   }
   ```

8. When all tasks are complete, run:

   `.specify/scripts/run-python.sh .specify/scripts/loopctl.py check implementation --record`

Use the returned action as the only completion decision.

## Safety Behavior

On macOS/Linux/WSL2, normal project edits and sandboxed checks proceed without
per-command confirmation. Native Windows has no OS sandbox, so normal Bash permission
prompts remain enabled.
Do not work around a deny, unsandbox a command, read credentials, use external network,
or invoke other desktop applications. Explain the boundary if a required check is blocked.
