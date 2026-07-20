# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

Keep the process proportional:
- For simple, obvious tasks, proceed directly.
- If evidence invalidates the plan, stop and revise it before continuing.
- Track progress in project task files only when the project already uses them or the user asks.

## 5. Verification Before Done

**Completion requires evidence, not confidence.**

- Run the most relevant tests, checks, or reproductions before declaring success.
- Verify behavior, not just syntax or compilation.
- Compare behavior before and after when the distinction matters.
- If verification is impossible, state what was not verified and why.
- Ask: "Would a staff engineer approve both the change and the evidence?"

## 6. Autonomous Problem Solving

**Investigate clear problems without unnecessary hand-holding.**

- For a clear bug report, reproduce it, identify the root cause, fix it, and verify the fix.
- Use available code, logs, errors, and failing tests to make progress independently.
- Prefer root-cause fixes over temporary workarounds.
- Ask when intended behavior is ambiguous, required access is missing, or options have materially different tradeoffs.

## 7. Deliberate Delegation

**Parallelize only when the work separates cleanly.**

- Use subagents for independent research, exploration, or analysis when parallel work adds real value.
- Give each subagent one focused task.
- Keep synthesis, consistency, and final verification with the main agent.

## 8. Learn from Corrections

**Turn mistakes into durable rules without creating needless process.**

- After a user correction, identify the pattern that caused the mistake and adjust the approach.
- If the project maintains a lessons file such as `tasks/lessons.md`, record a concise, reusable prevention rule.
- Review relevant existing lessons before similar work.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## 9. Four-Loop Operating Model

For feature work, use the project skills in this order:

1. `loop-requirements` until the requirements evidence passes, then request one intent approval.
2. `loop-design` until cross-artifact and architecture evidence passes, then request one execution approval.
3. `loop-implementation` on one independently testable slice at a time.
4. `loop-convergence` until the implementation is proven converged or the bounded budget escalates.

Read `.specify/loop-engineering/policy.json` before starting a loop. A non-zero
`loopctl.py` result is evidence to remediate or escalate, never a reason to bypass the
guard. Do not modify `.claude/settings.json`, `.claude/hooks/`, or the loop policy from
inside a Claude session. Do not deploy, publish, push, merge, or access external networks
unless the user separately authorizes that external effect and policy permits it.
