#!/usr/bin/env python3
"""Install the shared Loop Engineering runtime into one Spec Kit project."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys


GLOBAL_ROOT = Path(__file__).resolve().parent
TEMPLATE_ROOT = GLOBAL_ROOT / "project-template"


def is_template_constitution(text: str) -> bool:
    markers = ("[PROJECT_NAME]", "[PRINCIPLE_1_NAME]", "[GOVERNANCE_RULES]")
    return any(marker in text for marker in markers)


def backup_file(source: Path, project: Path, backup_root: Path) -> Path:
    relative = source.relative_to(project)
    destination = backup_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def install_file(
    source: Path,
    destination: Path,
    project: Path,
    backup_root: Path,
    *,
    preserve_established_constitution: bool = False,
) -> dict[str, str]:
    if not source.is_file():
        raise FileNotFoundError(f"Global template is missing: {source}")

    if destination.exists():
        if source.read_bytes() == destination.read_bytes():
            return {"path": str(destination), "action": "unchanged"}
        if preserve_established_constitution:
            current = destination.read_text(encoding="utf-8")
            if current.strip() and not is_template_constitution(current):
                return {"path": str(destination), "action": "preserved"}
        backup = backup_file(destination, project, backup_root)
    else:
        backup = None

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    result = {
        "path": str(destination),
        "action": "updated" if backup else "installed",
    }
    if backup:
        result["backup"] = str(backup)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--force-constitution", action="store_true")
    parser.add_argument(
        "--offline-init",
        action="store_true",
        help="Create a minimal Spec Kit structure when the CLI is unavailable",
    )
    args = parser.parse_args()

    project = Path(args.project_root).expanduser().resolve()
    if not (project / ".specify").is_dir():
        if args.offline_init:
            (project / ".specify").mkdir(parents=True, exist_ok=True)
        else:
            print(
                json.dumps(
                    {
                        "error": "Not a Spec Kit project",
                        "project": str(project),
                        "next": "specify init --here --integration claude --script sh",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 2

    if not project.is_dir():
        print(
            json.dumps(
                {
                    "error": "Project directory does not exist",
                    "project": str(project),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_root = project / ".specify/loop-engineering/backups" / timestamp
    mappings = (
        ("policy.json", ".specify/loop-engineering/policy.json", False),
        ("loopctl.py", ".specify/scripts/loopctl.py", False),
        ("run-python.sh", ".specify/scripts/run-python.sh", False),
        (
            "workflow.yml",
            ".specify/workflows/loop-engineering/workflow.yml",
            False,
        ),
        (
            "constitution.md",
            ".specify/memory/constitution.md",
            not args.force_constitution,
        ),
        ("templates/spec-template.md", ".specify/templates/spec-template.md", False),
        ("templates/plan-template.md", ".specify/templates/plan-template.md", False),
        ("templates/tasks-template.md", ".specify/templates/tasks-template.md", False),
        (
            "templates/checklist-template.md",
            ".specify/templates/checklist-template.md",
            False,
        ),
        (
            "templates/constitution-template.md",
            ".specify/templates/constitution-template.md",
            False,
        ),
        (
            "scripts/check-prerequisites.sh",
            ".specify/scripts/bash/check-prerequisites.sh",
            False,
        ),
        ("scripts/common.sh", ".specify/scripts/bash/common.sh", False),
        (
            "scripts/create-new-feature.sh",
            ".specify/scripts/bash/create-new-feature.sh",
            False,
        ),
        ("scripts/setup-plan.sh", ".specify/scripts/bash/setup-plan.sh", False),
        ("scripts/setup-tasks.sh", ".specify/scripts/bash/setup-tasks.sh", False),
    )

    changes = []
    for source_name, destination_name, preserve in mappings:
        changes.append(
            install_file(
                TEMPLATE_ROOT / source_name,
                project / destination_name,
                project,
                backup_root,
                preserve_established_constitution=preserve,
            )
        )

    init_options = project / ".specify/init-options.json"
    if not init_options.exists():
        init_options.write_text(
            json.dumps(
                {
                    "integration": "claude",
                    "script": "sh",
                    "feature_numbering": "sequential",
                    "portable_bundle": True,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        changes.append({"path": str(init_options), "action": "installed"})

    shell_scripts = list((project / ".specify/scripts/bash").glob("*.sh"))
    shell_scripts.append(project / ".specify/scripts/run-python.sh")
    for script in shell_scripts:
        if not script.exists():
            continue
        script.chmod(script.stat().st_mode | 0o100)

    if backup_root.exists() and not any(backup_root.rglob("*")):
        backup_root.rmdir()

    print(
        json.dumps(
            {
                "status": "ok",
                "project": str(project),
                "changes": changes,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
