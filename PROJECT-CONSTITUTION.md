# Agent Loop Engineering Constitution

## Core Principles

### I. Approved Intent Is the Source of Truth

The active `spec.md`, `plan.md`, and `tasks.md` define product intent and buildable
scope. Code, tests, and convergence findings MUST trace to those artifacts. Agents MUST
not silently change the specification to legitimize an implementation shortcut or add
unrequested scope.

### II. Evidence Before Completion

Every completion claim MUST cite ground truth from the environment: acceptance checks,
tests, static analysis, observable runtime behavior, or a traceable artifact check.
Model confidence, code inspection alone, and a self-authored summary are insufficient.
The change author MUST not silently waive evaluator findings.

### III. Bounded Evaluator–Optimizer Loops

Requirements, design, implementation, and convergence MUST each define a generator,
independent evaluators, an iteration budget, a measurable pass condition, stagnation
detection, and an escalation path. A loop MUST stop when it passes, exhausts its budget,
stagnates, invalidates an approved baseline, or crosses a protected capability boundary.

### IV. Least Privilege and Offline-by-Default Execution

Automated execution MUST be confined to the active project and session temporary
directory. Reading credentials, writing outside the project, external network access,
Unix sockets, desktop application control, privilege escalation, remote push/merge, and
deployment are denied unless an enterprise-managed policy explicitly grants a narrower
capability. An agent MUST NOT weaken or edit its own policy, hooks, or sandbox settings.

### V. Human Decisions Are Based on Impact

Humans approve product intent, architecture/dependencies/data changes, and irreversible
or external side effects. Ordinary project-local reads, edits, tests, linting, and static
checks SHOULD run automatically inside an OS-enforced sandbox when the platform supports
one. On native Windows without such a sandbox, normal command permission prompts MUST
remain enabled. Approval prompts MUST explain impact scope, reversibility, external
effects, and a safer alternative in plain language.

### VI. Learning Becomes Regression Evidence

A recurring failure MAY propose an evolution, but MUST NOT directly rewrite governance.
Promotion requires a reproducible failure or evaluation, root cause, proposed prevention
rule, false-positive analysis, rollback plan, human review, and a versioned policy change.
Accepted lessons SHOULD become deterministic checks before becoming longer prompts.

## Quality and Security Gates

- Requirements gate: no material ambiguity; FR/SC and acceptance scenarios are testable.
- Design gate: no CRITICAL/HIGH cross-artifact finding; tasks are traceable and
  independently verifiable; migrations and rollback are explicit.
- Implementation gate: relevant tests and checks pass; the diff stays within task scope.
- Convergence gate: zero actionable specified-scope gaps and current evidence is green.
- External-action gate: commit, publish, push, merge, release, deployment, production data
  change, or new trust relationship always requires explicit authority.

## Governance

This constitution supersedes agent prompts and workflow convenience. Amendments require a
written proposal with evidence, security review, rollback plan, and version increment.
Policy files and enforcing hooks are human-owned and MUST remain immutable to the running
agent. Exceptions expire and MUST identify owner, scope, reason, and end date.

**Version**: 1.0.0 | **Ratified**: 2026-07-20 | **Last Amended**: 2026-07-20
