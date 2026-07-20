#!/usr/bin/env python3
"""Portable installer for Spec Kit + bounded Loop Engineering on Claude Code."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


DENY_RULES = [
    "WebFetch",
    "mcp__*",
    "Bash(curl *)",
    "Bash(wget *)",
    "Bash(ssh *)",
    "Bash(scp *)",
    "Bash(nc *)",
    "Bash(ncat *)",
    "Bash(sudo *)",
    "Bash(su *)",
    "Bash(rm -rf *)",
    "Bash(git push *)",
    "Bash(gh pr merge *)",
    "Bash(kubectl *)",
    "Bash(terraform apply *)",
    "Bash(terraform destroy *)",
    "Bash(docker *)",
    "Bash(open *)",
    "Bash(osascript *)",
    "Bash(powershell *)",
    "Bash(powershell.exe *)",
    "Bash(pwsh *)",
    "Bash(pwsh.exe *)",
    "Bash(cmd *)",
    "Bash(cmd.exe *)",
    "Bash(bitsadmin *)",
    "Bash(bitsadmin.exe *)",
    "Bash(certutil *)",
    "Bash(certutil.exe *)",
    "Read(//**/.env)",
    "Read(//**/.env.*)",
    "Read(~/.ssh/**)",
    "Read(~/.aws/**)",
    "Read(~/.kube/**)",
    "Read(~/.docker/config.json)",
    "Read(~/.config/gcloud/**)",
    "Read(~/.netrc)",
    "Read(~/.npmrc)",
    "Edit(~/.claude/settings.json)",
    "Edit(~/.claude/hooks/**)",
    "Edit(~/.claude/loop-engineering/**)",
]

ASK_RULES = [
    "Bash(dangerouslyDisableSandbox:true)",
    "Bash(git commit *)",
    "Bash(git checkout *)",
    "Bash(git switch *)",
    "Bash(git merge *)",
    "Bash(git rebase *)",
    "Bash(npm install *)",
    "Bash(npm add *)",
    "Bash(pnpm install *)",
    "Bash(pnpm add *)",
    "Bash(yarn add *)",
    "Bash(pip install *)",
    "Bash(uv add *)",
    "Bash(cargo add *)",
    "Bash(go get *)",
    "Bash(chmod *)",
    "Bash(make install *)",
]

CREDENTIAL_FILES = [
    "~/.ssh",
    "~/.aws",
    "~/.kube",
    "~/.docker/config.json",
    "~/.config/gcloud",
    "~/.netrc",
    "~/.npmrc",
    "~/Library/Keychains",
    "~/AppData/Roaming/gcloud",
    "~/AppData/Roaming/Docker/config.json",
    "~/AppData/Local/Azure",
]

CREDENTIAL_ENV_VARS = [
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "NPM_TOKEN",
    "OPENAI_API_KEY",
]

GUIDANCE = """<!-- BEGIN PORTABLE SPEC KIT LOOP -->
## Portable Spec Kit + Four-Loop Operating Model

For non-trivial feature work, run `loop-init` once in the project, then use:

1. `loop-requirements` until evidence passes; approve product intent once.
2. `loop-design` until evidence passes; approve architecture/execution once.
3. `loop-implementation` one independently testable slice at a time.
4. `loop-convergence` until specified-scope gaps are zero or the budget escalates.

Never bypass a failed guard, weaken the sandbox, read credentials, access external
networks, or modify the Loop policy/Hook from inside Claude. Commit, publish, push,
merge, release, deployment, production data changes, and new trust relationships require
separate explicit authority.
<!-- END PORTABLE SPEC KIT LOOP -->
"""


def unique(existing: object, additions: list[str]) -> list[str]:
    values = (
        [item for item in existing if isinstance(item, str)]
        if isinstance(existing, list)
        else []
    )
    for addition in additions:
        if addition not in values:
            values.append(addition)
    return values


def atomic_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def load_settings(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def shell_command_path(path: Path) -> str:
    """Return a path usable by POSIX shells and Git Bash on native Windows."""
    return path.resolve().as_posix().replace('"', '\\"')


def merge_settings(
    settings: dict[str, object],
    claude_home: Path,
    *,
    platform_mode: str,
) -> dict[str, object]:
    permissions = settings.setdefault("permissions", {})
    if not isinstance(permissions, dict):
        raise ValueError("Existing permissions setting is not an object")
    permissions["defaultMode"] = (
        "default" if platform_mode == "native-windows" else "acceptEdits"
    )
    permissions["disableAutoMode"] = "disable"
    permissions["disableBypassPermissionsMode"] = "disable"
    permissions["deny"] = unique(permissions.get("deny"), DENY_RULES)
    permissions["ask"] = unique(permissions.get("ask"), ASK_RULES)

    sandbox = settings.setdefault("sandbox", {})
    if not isinstance(sandbox, dict):
        raise ValueError("Existing sandbox setting is not an object")
    if platform_mode == "native-windows":
        # Claude Code's OS-enforced Bash sandbox is unavailable on native Windows.
        # Keep normal permission prompts enabled rather than pretending commands are
        # isolated. WSL2 uses the strict branch below.
        sandbox.update(
            {
                "enabled": False,
                "failIfUnavailable": False,
                "autoAllowBashIfSandboxed": False,
                "allowUnsandboxedCommands": False,
            }
        )
    else:
        sandbox.update(
            {
                "enabled": True,
                "failIfUnavailable": True,
                "autoAllowBashIfSandboxed": True,
                "allowUnsandboxedCommands": False,
            }
        )

    filesystem = sandbox.setdefault("filesystem", {})
    if not isinstance(filesystem, dict):
        raise ValueError("Existing sandbox.filesystem setting is not an object")
    filesystem["denyRead"] = unique(filesystem.get("denyRead"), CREDENTIAL_FILES)
    filesystem["denyWrite"] = unique(
        filesystem.get("denyWrite"),
        ["~/.claude", "~/.ssh", "~/.aws", "~/.kube", "~/Library/Keychains"],
    )

    network = sandbox.setdefault("network", {})
    if not isinstance(network, dict):
        raise ValueError("Existing sandbox.network setting is not an object")
    network.update(
        {
            "allowedDomains": [],
            "deniedDomains": ["*"],
            "allowUnixSockets": [],
            "allowAllUnixSockets": False,
            "allowLocalBinding": False,
        }
    )

    credentials = sandbox.setdefault("credentials", {})
    if not isinstance(credentials, dict):
        raise ValueError("Existing sandbox.credentials setting is not an object")
    old_files = credentials.get("files") if isinstance(credentials.get("files"), list) else []
    old_env = credentials.get("envVars") if isinstance(credentials.get("envVars"), list) else []
    files = [item for item in old_files if isinstance(item, dict)]
    env_vars = [item for item in old_env if isinstance(item, dict)]
    known_files = {item.get("path") for item in files}
    known_env = {item.get("name") for item in env_vars}
    files.extend(
        {"path": path, "mode": "deny"}
        for path in CREDENTIAL_FILES
        if path not in known_files
    )
    env_vars.extend(
        {"name": name, "mode": "deny"}
        for name in CREDENTIAL_ENV_VARS
        if name not in known_env
    )
    credentials["files"] = files
    credentials["envVars"] = env_vars

    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("Existing hooks setting is not an object")
    pre_tool = hooks.setdefault("PreToolUse", [])
    if not isinstance(pre_tool, list):
        raise ValueError("Existing hooks.PreToolUse setting is not an array")
    hook_command = (
        f'"{shell_command_path(Path(sys.executable))}" '
        f'"{shell_command_path(claude_home / "hooks/security_guard.py")}"'
    )
    hook_found = False
    cleaned_groups = []
    for group in pre_tool:
        if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
            cleaned_groups.append(group)
            continue
        cleaned_handlers = []
        for handler in group["hooks"]:
            handler_command = handler.get("command") if isinstance(handler, dict) else None
            is_ours = (
                isinstance(handler_command, str)
                and "security_guard.py" in handler_command.replace("\\\\", "/")
            )
            if is_ours and hook_found:
                continue
            if is_ours:
                hook_found = True
            cleaned_handlers.append(handler)
        if cleaned_handlers:
            cleaned_group = dict(group)
            cleaned_group["hooks"] = cleaned_handlers
            cleaned_groups.append(cleaned_group)
    pre_tool[:] = cleaned_groups
    if not hook_found:
        pre_tool.append(
            {
                "matcher": "Bash|Edit|Write|Read|mcp__.*",
                "hooks": [
                    {
                        "type": "command",
                        "command": hook_command,
                        "timeout": 5,
                        "statusMessage": "正在按全局安全边界检查操作",
                    }
                ],
            }
        )
    return settings


def backup_file(path: Path, claude_home: Path, backup_root: Path) -> None:
    if not path.is_file():
        return
    try:
        relative = path.relative_to(claude_home)
    except ValueError:
        return
    destination = backup_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)
    if path.name == "settings.json":
        destination.chmod(0o600)


def copy_capsule(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Bundle file missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--claude-home", default=str(Path.home() / ".claude"))
    parser.add_argument(
        "--platform-mode",
        choices=("strict", "native-windows"),
        default="strict",
        help="Use native-windows when Claude runs outside WSL2",
    )
    args = parser.parse_args()

    bundle = Path(args.bundle_root).expanduser().resolve()
    claude_home = Path(args.claude_home).expanduser().resolve()
    settings_path = claude_home / "settings.json"
    guidance_path = claude_home / "CLAUDE.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_root = claude_home / "backups" / f"portable-loop-{timestamp}"
    backup_root.mkdir(parents=True, exist_ok=False)
    backup_root.chmod(0o700)

    managed_targets = [settings_path, guidance_path, claude_home / "hooks/security_guard.py"]
    managed_targets.extend(
        claude_home / "skills" / path.parent.name / "SKILL.md"
        for path in sorted((bundle / "skills").glob("*/SKILL.md"))
    )
    managed_targets.extend(
        [
            claude_home / "loop-engineering/policy.json",
            claude_home / "loop-engineering/loopctl.py",
            claude_home / "loop-engineering/bootstrap_project.py",
            claude_home / "loop-engineering/run-python.sh",
        ]
    )
    for target in managed_targets:
        backup_file(target, claude_home, backup_root)

    settings = merge_settings(
        load_settings(settings_path),
        claude_home,
        platform_mode=args.platform_mode,
    )
    atomic_json(settings_path, settings)

    copy_capsule(
        bundle / "runtime/security_guard.py.md",
        claude_home / "hooks/security_guard.py",
    )
    installed_skills = []
    for source in sorted((bundle / "skills").glob("*/SKILL.md")):
        skill_name = source.parent.name
        copy_capsule(source, claude_home / "skills" / skill_name / "SKILL.md")
        installed_skills.append(skill_name)

    runtime = claude_home / "loop-engineering"
    template = runtime / "project-template"
    copy_capsule(bundle / "runtime/policy.json.md", runtime / "policy.json")
    copy_capsule(bundle / "runtime/loopctl.py.md", runtime / "loopctl.py")
    copy_capsule(bundle / "runtime/run-python.sh.md", runtime / "run-python.sh")
    (runtime / "run-python.sh").chmod((runtime / "run-python.sh").stat().st_mode | 0o100)
    copy_capsule(
        bundle / "runtime/bootstrap_project.py.md",
        runtime / "bootstrap_project.py",
    )
    copy_capsule(bundle / "runtime/policy.json.md", template / "policy.json")
    copy_capsule(bundle / "runtime/loopctl.py.md", template / "loopctl.py")
    copy_capsule(bundle / "runtime/run-python.sh.md", template / "run-python.sh")
    copy_capsule(bundle / "runtime/workflow.yml.md", template / "workflow.yml")
    copy_capsule(bundle / "PROJECT-CONSTITUTION.md", template / "constitution.md")
    for source in sorted((bundle / "project-templates").glob("*.md")):
        copy_capsule(source, template / "templates" / source.name)
    for source in sorted((bundle / "spec-kit-scripts").glob("*.sh.md")):
        destination = template / "scripts" / source.name.removesuffix(".md")
        copy_capsule(source, destination)
        destination.chmod(destination.stat().st_mode | 0o100)

    copy_capsule(bundle / "README.md", runtime / "README.md")
    copy_capsule(bundle / "CLAUDE.md", runtime / "BUNDLE-CLAUDE.md")

    existing_guidance = (
        guidance_path.read_text(encoding="utf-8") if guidance_path.exists() else "# CLAUDE.md\n"
    )
    if "<!-- BEGIN PORTABLE SPEC KIT LOOP -->" not in existing_guidance:
        guidance_path.parent.mkdir(parents=True, exist_ok=True)
        guidance_path.write_text(
            existing_guidance.rstrip() + "\n\n" + GUIDANCE + "\n",
            encoding="utf-8",
        )

    manifest = {
        "schema_version": "1.0",
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "bundle": str(bundle),
        "backup": str(backup_root),
        "skills": installed_skills,
        "platform_mode": args.platform_mode,
        "strict_offline": args.platform_mode == "strict",
        "preserved_settings_keys": sorted(settings.keys()),
    }
    atomic_json(runtime / "install-manifest.json", manifest)
    print(json.dumps({"status": "installed", **manifest}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
