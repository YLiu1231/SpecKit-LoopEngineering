---
name: "loop-requirements"
description: "Run a bounded Spec Kit requirements loop: draft intent, align material decisions with the user through grilling rounds, evaluate with deterministic guards, and stop or escalate with evidence."
argument-hint: "Describe the feature or the requirements problem to resolve"
compatibility: "Requires Spec Kit project structure and the speckit skills"
user-invocable: true
disable-model-invocation: false
---

# Requirements Loop

Turn the user's feature description into an approved, testable statement of
intent. This is an evaluator–optimizer loop, not a linear sequence.

## Contract

- Generator: `speckit-specify`, then `speckit-clarify` when material ambiguity remains.
- Evaluators: the Spec Kit requirements checklist, an adversarial checklist pass,
  and `.specify/scripts/loopctl.py check requirements --record`.
- Budget: read `loops.requirements` from
  `.specify/loop-engineering/policy.json`; never exceed it.
- Authority: `spec.md` is product intent. Do not put frameworks, code structure,
  or implementation preferences into it.
- Alignment method: before design, map material product decisions as a design tree
  and use bounded grilling rounds until its frontier is empty. Facts are the agent's
  job; use available project evidence and tools instead of asking the user to research.
- Human gate: the user owns decisions that materially change scope, security/privacy,
  compliance, irreversible data behavior, user-visible semantics, exclusions, or
  measurable success. Ask at most three current-frontier decisions per round and give
  a recommended answer with its tradeoff.
- Grilling and remediation share the requirements iteration budget; do not create a
  second unbounded interview loop.

## Loop

1. Invoke `speckit-specify` with `$ARGUMENTS` when no active spec exists; otherwise
   use the active `spec.md` as the generator input.
2. Perform a read-only ambiguity scan. Separate facts, assumptions, decisions, and
   out-of-scope items. Resolve discoverable facts yourself. Invoke `speckit-clarify`
   only for material unresolved decisions.
3. Build a design tree rooted in product intent. Its frontier contains only material
   decisions whose prerequisites are settled. Ask a numbered grilling round for up to
   three highest-impact frontier decisions, each with a recommended answer and the
   consequence of choosing it. Wait for the user's answers, update `spec.md`, recompute
   the frontier, and continue within the shared budget. Do not ask downstream questions
   while a prerequisite is unsettled.
4. When the frontier is empty, record the settled baseline in `spec.md`: users and
   outcomes, scope and exclusions, user-visible behavior, security/privacy assumptions,
   failure semantics, and measurable success. Do not enter `loop-design`; the final
   intent approval comes only after the evaluators pass.
5. Run `speckit-checklist` as an adversarial evaluator. Check at least:
   happy paths, failure paths, authorization/privacy, observability, scale limits,
   compatibility, and measurable success. During this evaluator pass, do not edit.
6. Feed only specific failed checks back to the generator. Make the smallest edit
   that resolves them; do not broaden scope. If a failed check exposes a new material
   product decision, add it to the design tree and return to the grilling frontier.
7. Run:

   `.specify/scripts/run-python.sh .specify/scripts/loopctl.py check requirements --record`

8. Interpret the returned control action:
   - `stop-pass`: report the evidence and final product-intent baseline, then request
     the single intent approval. Only explicit user approval satisfies the gate and
     permits `loop-design`.
   - `continue`: repeat from the failed checks, not from scratch.
   - `escalate-*`: stop. Show the unresolved decisions, evidence, iteration count,
     and the smallest user decision that can unblock progress.

## Exit Evidence

Return the feature directory, FR/SC counts, checklist result, deterministic score,
settled decisions, deferred or out-of-scope branches, assumptions made, and any
residual risk. Confidence alone is not evidence.
