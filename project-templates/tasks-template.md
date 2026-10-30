---
description: "Incremental tasks with mandatory US selftests and whole-project verification"
---

# Tasks: [FEATURE]

**Inputs**: approved spec.md, plan.md, us-design.md, compatibility.md, context-lock.json.
**Traceability**: keep traceability.json aligned with FR → US → task → catalog case IDs.
**Tests are required** for each US and every increment. Do not turn failures into exclusions.

## Format

Use `- [ ] T001 [P] [US1] Description with repository path and evidence`.
[P] means independent paths and no incomplete prerequisites. Setup/shared tasks may omit a US label.
Replace all placeholders with actual project tasks; never copy examples as completed work.

## Baseline and necessary preparation

- [ ] T001 Check current project facts, approved constraints and target dependency set.
- [ ] T002 Record relevant existing failures and full-case coverage gaps without hiding them.
- [ ] T003 Configure actual runner output parsing and project resource budget.

Only include preparation required for this increment; do not recreate established infrastructure.

## US1 — [Business outcome]

**Requirement IDs**: [FR-001]
**Cases**: [stable IDs in .specify/selftests/catalog.yaml]
**Expected behavior**: [normal, error, boundary and applicable compatibility assertions]

- [ ] T010 [US1] Add/update real assertion-bearing tests in [test path].
- [ ] T011 [US1] Implement [behavior] in [code path].
- [ ] T012 [US1] Execute story tests and preserve actual outputs; resolve or route findings.

[Repeat for every approved US. Planned initial TDD red is not a failed remediation attempt.]

## Whole increment verification and handoff

- [ ] T090 Run the entire registered functional catalog: existing, new and compatibility cases.
- [ ] T091 Classify fail/skip/error/not-run separately and preserve decisions for accepted risks.
- [ ] T092 Check final behavior inputs against evidence; rerun full catalog after behavior changes.
- [ ] T093 Refresh current knowledge and boundaries; retain feature history and decisions.
- [ ] T094 Publish version-bound handoff or explicit no-external-change assessment in this repository.
- [ ] T095 Evaluate implementation/convergence gates using runtime evidence, not a written PASS.

## Dependencies and completion

[Record actual US dependencies and safe parallel work. Conflicting boundary decisions block only affected work.]
Every task has an observable result. A checked task, zero exit code or risk acceptance does not prove
full-case success. Missing prescribed execution blocks implementation/convergence completion.
Commit, merge and deployment are separate authorized actions.
