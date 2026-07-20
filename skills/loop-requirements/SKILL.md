---
name: "loop-requirements"
description: "Run a bounded Spec Kit requirements loop: specify, clarify only material ambiguity, evaluate with checklists and deterministic guards, and stop or escalate with evidence."
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
- Human gate: ask only when alternatives materially change scope, security/privacy,
  compliance, irreversible data behavior, or user-visible semantics. Group at most
  three decisions into one request.

## Loop

1. Invoke `speckit-specify` with `$ARGUMENTS` when no active spec exists; otherwise
   use the active `spec.md` as the generator input.
2. Perform a read-only ambiguity scan. Separate facts, assumptions, decisions, and
   out-of-scope items. Invoke `speckit-clarify` only for material unresolved decisions.
3. Run `speckit-checklist` as an adversarial evaluator. Check at least:
   happy paths, failure paths, authorization/privacy, observability, scale limits,
   compatibility, and measurable success. During this evaluator pass, do not edit.
4. Feed only specific failed checks back to the generator. Make the smallest edit
   that resolves them; do not broaden scope.
5. Run:

   `.specify/scripts/run-python.sh .specify/scripts/loopctl.py check requirements --record`

6. Interpret the returned control action:
   - `stop-pass`: report the evidence and request the single product-intent gate.
   - `continue`: repeat from the failed checks, not from scratch.
   - `escalate-*`: stop. Show the unresolved decisions, evidence, iteration count,
     and the smallest user decision that can unblock progress.

## Exit Evidence

Return the feature directory, FR/SC counts, checklist result, deterministic score,
assumptions made, and any residual risk. Confidence alone is not evidence.
