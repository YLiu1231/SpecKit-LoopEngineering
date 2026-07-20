# Bundle Manifest

## Release

- Name: `claude-speckit-loop-bundle`
- Version: `1.1.0`
- Build date: `2026-07-21`
- Default installer network behavior: no download
- Runtime network boundary: OS-enforced offline on macOS/Linux/WSL2; deny/Hook guard on native Windows
- Secrets included: none
- Upstream Spec Kit license: MIT; see `SPEC-KIT-LICENSE.md`
- Repository license: MIT; see `LICENSE.md`

## Components

- 10 Spec Kit skills
- 5 Loop Engineering skills, including `loop-init`
- 5 Spec Kit project templates
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
find . -type f ! -name '*.md' ! -name 'install.sh' ! -name 'install.ps1' -print
sh -n install.sh
./install.sh doctor
```

The first command must print nothing. Review `runtime/*.md` before distribution: these are
plain-text code capsules restored to their native extensions only during installation.

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
