---
name: "loop-init"
description: "Install or update the global Loop Engineering runtime in the current Spec Kit project without replacing an established project constitution."
argument-hint: "Optional: use --force-constitution only when intentionally replacing the current constitution"
compatibility: "Requires the global ~/.claude/loop-engineering runtime; Windows native uses Git Bash"
user-invocable: true
disable-model-invocation: false
---

# Initialize Loop Engineering in the Current Project

1. Confirm the current working directory is the intended project root.
2. If `.specify/` does not exist and the `specify` CLI is available, run:

   `specify init --here --integration claude --script sh`

   Do not add `--force` automatically. If the CLI is unavailable, use the bundled
   offline initializer by adding `--offline-init` to the bootstrap command below.
3. Run the global bootstrapper from the project root:

   `"$HOME/.claude/loop-engineering/run-python.sh" "$HOME/.claude/loop-engineering/bootstrap_project.py"`

4. If `$ARGUMENTS` explicitly contains `--force-constitution`, pass that flag through.
   Otherwise preserve any non-template constitution already owned by the project.
5. Run these verification checks:

   - `.specify/scripts/run-python.sh -m py_compile .specify/scripts/loopctl.py`
   - `specify workflow info loop-engineering`
   - `.specify/scripts/run-python.sh .specify/scripts/loopctl.py --help`

6. Report which files were installed, updated, preserved, or backed up. Do not start a
   feature or modify product code as part of initialization.
