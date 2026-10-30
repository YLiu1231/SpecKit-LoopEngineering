# Bundle Manifest

## Release

- Name: `claude-speckit-loop-bundle`
- Version: `2.0.0`
- Build date: `2026-10-29`
- Default installer network behavior: no download
- Runtime network boundary: OS-enforced offline on macOS/Linux/WSL2; deny/Hook guard on native Windows
- Secrets included: none
- Upstream Spec Kit license: MIT; see `SPEC-KIT-LICENSE.md`
- Repository license: MIT; see `LICENSE.md`

## Components

- 10 Spec Kit skills
- 5 Loop Engineering skills, including `loop-init`
- 5 Spec Kit project templates plus incremental JSON/Markdown examples
- Dependency-free incremental Python package under `runtime/loop_runtime/`
- Local Git integration tests and incremental operation documentation
- 5 Spec Kit offline shell capsules
- Cross-platform Python launcher capsule
- Global security Hook capsule
- Loop policy, controller, project bootstrapper and workflow capsules
- Global/project CLAUDE governance documents
- POSIX/WSL2 entry point: `install.sh`
- Native Windows PowerShell entry point: `install.ps1`

## Audit Commands

Run from the bundle root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
sh -n install.sh
git diff --check
```

Review `runtime/*.md` capsules and `runtime/loop_runtime/*.py` before distribution.
The package now contains native Python/JSON sources; it is no longer Markdown-only.

On native Windows, run `install.ps1 doctor` and use a PowerShell parser or PSScriptAnalyzer
approved by your organization before distribution.

## Trust Boundary

The installers write only to the selected `CLAUDE_HOME` and an explicitly selected
project directory. They preserve existing Claude settings keys, make a timestamped backup,
do not print environment-variable values, and do not modify `/Library`, `/etc`, the Windows
registry, MDM, system binaries, system trust stores, or shell profiles.

Strict OS-enforced sandbox mode applies to macOS, Linux, and WSL2. Native Windows uses
normal Bash permission prompts, deny rules, and the policy Hook because Claude Code does
not provide its OS sandbox on native Windows.
