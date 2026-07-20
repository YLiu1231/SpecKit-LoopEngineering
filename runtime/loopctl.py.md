#!/usr/bin/env python3
"""Deterministic guardrails for the four Spec Kit engineering loops.

This tool does not generate product content and does not execute project tests.
It checks artifact contracts, records bounded iteration state, detects
stagnation, and creates reviewable evolution proposals.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Callable


def discover_project_root() -> Path:
    """Resolve the active Spec Kit project for local or global installation."""
    candidates: list[Path] = []
    configured = os.environ.get("CLAUDE_PROJECT_DIR")
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend([Path.cwd(), *Path.cwd().parents])
    script_path = Path(__file__).resolve()
    if len(script_path.parents) >= 3:
        candidates.append(script_path.parents[2])
    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved / ".specify").is_dir():
            return resolved
    return Path.cwd().resolve()


PROJECT_ROOT = discover_project_root()
PROJECT_POLICY_PATH = PROJECT_ROOT / ".specify/loop-engineering/policy.json"
GLOBAL_POLICY_PATH = Path.home() / ".claude/loop-engineering/policy.json"
POLICY_PATH = (
    PROJECT_POLICY_PATH if PROJECT_POLICY_PATH.exists() else GLOBAL_POLICY_PATH
)
LOOP_NAMES = ("requirements", "design", "implementation", "convergence")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def resolve_feature_dir(raw: str | None) -> Path:
    if raw:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        return candidate.resolve()

    pointer = PROJECT_ROOT / ".specify/feature.json"
    if pointer.exists():
        value = read_json(pointer).get("feature_directory")
        if isinstance(value, str) and value:
            candidate = Path(value)
            if not candidate.is_absolute():
                candidate = PROJECT_ROOT / candidate
            return candidate.resolve()
    raise ValueError(
        "No active feature. Pass --feature-dir or run /speckit-specify first."
    )


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def checked_items(text: str) -> tuple[int, int]:
    all_items = re.findall(r"^\s*-\s*\[[ xX]\]", text, flags=re.MULTILINE)
    done_items = re.findall(r"^\s*-\s*\[[xX]\]", text, flags=re.MULTILINE)
    return len(done_items), len(all_items)


def result(loop: str, checks: list[tuple[str, bool, str]]) -> dict[str, Any]:
    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)
    score = round(passed / total, 4) if total else 0.0
    return {
        "loop": loop,
        "status": "PASS" if passed == total else "FAIL",
        "score": score,
        "passed": passed,
        "total": total,
        "checks": [
            {"id": check_id, "passed": ok, "evidence": evidence}
            for check_id, ok, evidence in checks
        ],
    }


def check_requirements(feature: Path) -> dict[str, Any]:
    spec_path = feature / "spec.md"
    spec = read_text(spec_path)
    checklist_path = feature / "checklists/requirements.md"
    checklist = read_text(checklist_path)
    done, total = checked_items(checklist)
    marker_count = len(re.findall(r"\[NEEDS CLARIFICATION(?::[^\]]*)?\]", spec))
    fr_count = len(set(re.findall(r"\bFR-\d{3}\b", spec)))
    sc_count = len(set(re.findall(r"\bSC-\d{3}\b", spec)))
    return result(
        "requirements",
        [
            ("spec-exists", bool(spec.strip()), str(spec_path)),
            (
                "user-scenarios",
                bool(re.search(r"User Scenarios|User Stories|用户场景|用户故事", spec, re.I)),
                "user scenario section present",
            ),
            ("functional-requirements", fr_count > 0, f"FR count={fr_count}"),
            ("success-criteria", sc_count > 0, f"SC count={sc_count}"),
            ("no-clarification-markers", marker_count == 0, f"markers={marker_count}"),
            ("quality-checklist-exists", bool(checklist.strip()), str(checklist_path)),
            (
                "quality-checklist-passes",
                total > 0 and done == total,
                f"checked={done}/{total}",
            ),
        ],
    )


def check_design(feature: Path) -> dict[str, Any]:
    spec = read_text(feature / "spec.md")
    plan_path = feature / "plan.md"
    tasks_path = feature / "tasks.md"
    analysis_path = feature / "analysis.md"
    plan = read_text(plan_path)
    tasks = read_text(tasks_path)
    analysis = read_text(analysis_path)
    task_ids = re.findall(r"^\s*-\s*\[[ xX]\]\s+(T\d{3})\b", tasks, re.M)
    duplicates = sorted({item for item in task_ids if task_ids.count(item) > 1})
    clarity_markers = sum(
        len(re.findall(r"\[NEEDS CLARIFICATION(?::[^\]]*)?\]", text))
        for text in (spec, plan, tasks)
    )
    return result(
        "design",
        [
            ("plan-exists", bool(plan.strip()), str(plan_path)),
            ("tasks-exist", bool(tasks.strip()), str(tasks_path)),
            ("task-ids", bool(task_ids), f"task count={len(task_ids)}"),
            ("unique-task-ids", not duplicates, f"duplicates={duplicates}"),
            (
                "independent-test-criteria",
                bool(re.search(r"independent test|独立测试|acceptance|验收", tasks, re.I)),
                "tasks include independently verifiable outcomes",
            ),
            ("no-clarification-markers", clarity_markers == 0, f"markers={clarity_markers}"),
            ("analysis-report-exists", bool(analysis.strip()), str(analysis_path)),
            (
                "analysis-gate-passes",
                bool(re.search(r"^Gate-Result:\s*PASS\s*$", analysis, re.I | re.M)),
                "analysis.md contains Gate-Result: PASS",
            ),
        ],
    )


def implementation_evidence(feature: Path) -> tuple[bool, str]:
    evidence_path = feature / "evidence/implementation.json"
    if not evidence_path.exists():
        return False, f"missing {evidence_path}"
    try:
        evidence = read_json(evidence_path)
    except ValueError as exc:
        return False, str(exc)
    commands = evidence.get("commands")
    if not isinstance(commands, list) or not commands:
        return False, "commands evidence is empty"
    bad = [
        index
        for index, item in enumerate(commands)
        if not isinstance(item, dict) or item.get("exit_code") != 0
    ]
    return not bad, f"commands={len(commands)}, failing indexes={bad}"


def check_implementation(feature: Path) -> dict[str, Any]:
    tasks_path = feature / "tasks.md"
    tasks = read_text(tasks_path)
    done, total = checked_items(tasks)
    evidence_ok, evidence_note = implementation_evidence(feature)
    return result(
        "implementation",
        [
            ("tasks-exist", total > 0, f"tasks={total}"),
            ("all-tasks-complete", total > 0 and done == total, f"checked={done}/{total}"),
            ("verification-evidence", evidence_ok, evidence_note),
        ],
    )


def check_convergence(feature: Path) -> dict[str, Any]:
    implementation = check_implementation(feature)
    convergence_path = feature / "convergence.md"
    convergence = read_text(convergence_path)
    findings = len(
        re.findall(r"^\s*-\s*\[[ ]\].*(?:missing|partial|contradicts)", convergence, re.I | re.M)
    )
    return result(
        "convergence",
        [
            (
                "implementation-gate-passes",
                implementation["status"] == "PASS",
                f"implementation score={implementation['score']}",
            ),
            ("convergence-report-exists", bool(convergence.strip()), str(convergence_path)),
            (
                "convergence-declared",
                bool(re.search(r"^Status:\s*CONVERGED\s*$", convergence, re.I | re.M)),
                "convergence.md contains Status: CONVERGED",
            ),
            ("no-open-findings", findings == 0, f"open findings={findings}"),
        ],
    )


CHECKERS: dict[str, Callable[[Path], dict[str, Any]]] = {
    "requirements": check_requirements,
    "design": check_design,
    "implementation": check_implementation,
    "convergence": check_convergence,
}


def load_state(feature: Path) -> dict[str, Any]:
    path = feature / "loop-state.json"
    if path.exists():
        return read_json(path)
    return {
        "schema_version": "1.0",
        "feature_directory": str(feature),
        "policy_version": read_json(POLICY_PATH).get("policy_version"),
        "loops": {},
        "updated_at": None,
    }


def record_result(feature: Path, evaluation: dict[str, Any]) -> dict[str, Any]:
    policy = read_json(POLICY_PATH)
    loop = str(evaluation["loop"])
    loop_policy = policy["loops"][loop]
    state = load_state(feature)
    entry = state.setdefault("loops", {}).setdefault(
        loop,
        {"iterations": 0, "stagnant_iterations": 0, "best_score": 0.0, "history": []},
    )
    previous_score = float(entry["history"][-1]["score"]) if entry["history"] else 0.0
    current_score = float(evaluation["score"])
    delta = current_score - previous_score
    entry["iterations"] += 1
    if entry["iterations"] > 1 and delta < float(loop_policy["min_score_delta"]):
        entry["stagnant_iterations"] += 1
    else:
        entry["stagnant_iterations"] = 0
    entry["best_score"] = max(float(entry["best_score"]), current_score)

    if evaluation["status"] == "PASS":
        action = "stop-pass"
    elif entry["iterations"] >= int(loop_policy["max_iterations"]):
        action = "escalate-budget-exhausted"
    elif entry["stagnant_iterations"] >= int(loop_policy["max_stagnant_iterations"]):
        action = "escalate-stagnation"
    else:
        action = "continue"

    timestamp = datetime.now(timezone.utc).isoformat()
    entry["status"] = evaluation["status"]
    entry["action"] = action
    entry["history"].append(
        {
            "iteration": entry["iterations"],
            "timestamp": timestamp,
            "status": evaluation["status"],
            "score": current_score,
            "delta": round(delta, 4),
            "failed_checks": [
                item["id"] for item in evaluation["checks"] if not item["passed"]
            ],
        }
    )
    state["updated_at"] = timestamp
    atomic_write_json(feature / "loop-state.json", state)
    return {"loop": loop, "action": action, "state": entry}


def command_check(args: argparse.Namespace) -> int:
    feature = resolve_feature_dir(args.feature_dir)
    evaluation = CHECKERS[args.loop](feature)
    output: dict[str, Any] = {"evaluation": evaluation}
    if args.record:
        output["control"] = record_result(feature, evaluation)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if evaluation["status"] == "PASS":
        return 0
    if output.get("control", {}).get("action", "").startswith("escalate"):
        return 2
    return 1


def command_status(args: argparse.Namespace) -> int:
    feature = resolve_feature_dir(args.feature_dir)
    print(json.dumps(load_state(feature), ensure_ascii=False, indent=2))
    return 0


def command_propose(args: argparse.Namespace) -> int:
    feature = resolve_feature_dir(args.feature_dir)
    now = datetime.now(timezone.utc)
    proposal = {
        "schema_version": "1.0",
        "status": "proposed",
        "created_at": now.isoformat(),
        "feature_directory": str(feature),
        "failure": args.failure,
        "reproduction_or_eval": args.evidence,
        "root_cause": args.root_cause,
        "candidate_rule": args.rule,
        "false_positive_analysis": args.false_positive_analysis,
        "rollback_plan": args.rollback,
        "automatic_policy_change": False,
    }
    slug = re.sub(r"[^a-z0-9]+", "-", args.failure.lower()).strip("-")[:48] or "proposal"
    path = PROJECT_ROOT / ".specify/loop-engineering/proposals" / f"{now:%Y%m%dT%H%M%SZ}-{slug}.json"
    atomic_write_json(path, proposal)
    print(json.dumps({"proposal": str(path), "status": "awaiting-human-review"}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Evaluate one loop's artifact contract")
    check.add_argument("loop", choices=LOOP_NAMES)
    check.add_argument("--feature-dir")
    check.add_argument("--record", action="store_true")
    check.set_defaults(func=command_check)

    status = subparsers.add_parser("status", help="Show bounded-loop state")
    status.add_argument("--feature-dir")
    status.set_defaults(func=command_status)

    propose = subparsers.add_parser(
        "propose-evolution", help="Create a reviewable learning proposal"
    )
    propose.add_argument("--feature-dir")
    propose.add_argument("--failure", required=True)
    propose.add_argument("--evidence", required=True)
    propose.add_argument("--root-cause", required=True)
    propose.add_argument("--rule", required=True)
    propose.add_argument("--false-positive-analysis", required=True)
    propose.add_argument("--rollback", required=True)
    propose.set_defaults(func=command_propose)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return int(args.func(args))
    except (KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
