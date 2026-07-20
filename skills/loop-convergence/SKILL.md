---
name: "loop-convergence"
description: "Run a bounded Spec Kit convergence loop: assess present code against intent, append traceable gaps, implement them, and prove convergence without endless task growth."
argument-hint: "Optional convergence focus or residual-risk constraint"
compatibility: "Requires an active feature after at least one implementation pass"
user-invocable: true
disable-model-invocation: false
---

# Convergence Loop

Close verified gaps without turning convergence into an infinite backlog generator.

## Contract

- Generator: `speckit-implement` applied to traceable remaining tasks.
- Evaluators: the real test/evidence suite plus `speckit-converge`, which may only
  append tasks, and `.specify/scripts/loopctl.py check convergence --record`.
- Budget: read `loops.convergence`; enforce both the iteration limit and
  `max_new_tasks_per_iteration`.
- Scope is frozen to the approved spec, plan, tasks, and constitution. New ideas are
  follow-up proposals, not convergence findings.
- Human gate: accepting residual risk or release/deployment. No gate for ordinary
  project-local fixes and checks.

## Loop

1. Run the same deterministic implementation evidence suite used by
   `loop-implementation`. Never converge on stale or missing evidence.
2. Invoke `speckit-converge` as a read-only assessor except for its append-only write to
   `tasks.md`. Classify gaps as missing, partial, contradicts, or unrequested, with a
   source reference and concrete code evidence.
3. If new tasks are appended:
   - reject duplicates and items without a source reference;
   - cap the batch at the policy limit, ordered CRITICAL/HIGH first;
   - invoke `speckit-implement` or `loop-implementation` on the smallest slice;
   - rerun tests and repeat.
4. If no gaps remain, write the active feature's `convergence.md` with checked scope,
   test evidence references, zero open findings, residual risks, and exactly:

   `Status: CONVERGED`

5. Run:

   `.specify/scripts/run-python.sh .specify/scripts/loopctl.py check convergence --record`

6. `stop-pass` is the only clean completion. On stagnation or exhausted budget, stop
   and present unresolved findings; do not append another speculative phase.

## Evolution Handoff

When a failure pattern should improve future projects, do not edit the policy, hook,
constitution, or skills in-session. Create a proposal with
`.specify/scripts/loopctl.py propose-evolution` containing a reproduction/eval, root
cause, prevention rule, false-positive analysis, and rollback. Promotion is a separate
human-reviewed policy change.
