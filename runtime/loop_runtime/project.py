"""Local project inventory, refreshable knowledge and version-bound context.

Only registered local repositories are read. No command here fetches repositories,
executes discovered entry points, or interprets Markdown as instructions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
from typing import Any

from .common import load, save, safe, digest, file_digest, now, identifier, read_record, write_record, parse

SCHEMA = "1.0"
AUTO_START = "<!-- loop:observed-facts:start -->"
AUTO_END = "<!-- loop:observed-facts:end -->"
EXCLUDED_DIRS = {".git", ".credentials", ".aws", ".ssh", ".kube", ".docker", ".venv", "venv", "node_modules", "__pycache__"}
SECRET_NAMES = {".env", ".netrc", ".npmrc", "auth.json", "settings.local.json", "credentials", "credentials.json", "secrets.json", "secrets.yaml", "id_rsa", "id_ed25519"}
GENERATED_PREFIXES = (".specify/knowledge/", ".specify/local/", ".specify/exchange/", ".specify/releases/")
FEATURE_OUTPUTS = {"context-lock.json", "decisions.json", "findings.json", "loop-state.json", "analysis.md", "convergence.md", "budget.json", "gate-state.json", "handoff.json", "receipt.json"}


def production_baselines(root):
    from .exchange import release_status
    records = []
    for env in sorted(_config(root).get("release_authority", {})):
        status = release_status(root, env)
        # Unrelated commits at the authority ref do not change the release fact.
        status.pop("authority_commit", None); status.pop("history_count", None)
        records.append({"project_id": _config(root)["project_id"], **status})
    return records


def baseline_project(args):
    from .evidence import run_suite
    root = _root(args)
    feature = safe(root, args.feature_dir)
    feature.mkdir(parents=True, exist_ok=True)
    result = run_suite(root, feature, args.catalog)
    save(safe(root, ".specify/knowledge/baseline.json"), result)
    refreshed = refresh_knowledge(args)
    return {"ok": True, "baseline": result, "knowledge": refreshed,
            "note": "Baseline failures and gaps remain visible; initialization does not require repairing historical issues."}


def _git(root: Path, *args: str, required: bool = True) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=30)
    if result.returncode:
        if required:
            raise ValueError("local Git operation failed: " + " ".join(args[:2]))
        return ""
    text = result.stdout.decode("utf-8", errors="replace")
    return text if "-z" in args else text.strip()


def _root(args: argparse.Namespace) -> Path:
    root = Path(args.root).absolute()
    if root.is_symlink():
        raise ValueError("project root must not be a symlink")
    root = root.resolve()
    if Path(_git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise ValueError("root must be the Git repository root")
    return root


def _allowed(relative: str) -> bool:
    path = Path(relative)
    return not (any(part in EXCLUDED_DIRS for part in path.parts)
                or path.name in SECRET_NAMES or path.name.startswith(".env.")
                or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"})


def _config(root: Path) -> dict[str, Any]:
    config = load(safe(root, ".specify/project.yaml"))
    if not isinstance(config, dict) or not config.get("project_id"):
        raise ValueError("initialize .specify/project.yaml first")
    identifier(config["project_id"])
    return config


def _files(root: Path) -> list[str]:
    raw = _git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    return sorted(set(raw.split("\0")) - {""})


def _snapshot(root: Path) -> dict[str, Any]:
    files, unknowns = [], []
    names = _files(root)
    for relative in names[:20000]:
        if not _allowed(relative):
            continue
        if relative.startswith(GENERATED_PREFIXES):
            continue
        if relative.startswith("specs/") and (Path(relative).name in FEATURE_OUTPUTS or "/evidence/" in relative):
            continue
        try:
            path = safe(root, relative)
            if not path.exists():
                files.append({"path": relative, "content_digest": None, "state": "deleted"})
                continue
            if not path.is_file():
                continue
            if path.stat().st_size > 20 * 1024 * 1024:
                unknowns.append({"path": relative, "reason": "file exceeds 20 MiB inventory limit"})
                continue
            files.append({"path": relative, "content_digest": file_digest(path)})
        except ValueError:
            unknowns.append({"path": relative, "reason": "unsafe path or symlink"})
    if len(names) > 20000:
        unknowns.append({"reason": "inventory truncated at 20000 paths", "total_paths": len(names)})
    return {"storage": "local_snapshot", "visibility": "local_only",
            "base_commit": _git(root, "rev-parse", "HEAD", required=False) or None,
            "branch": _git(root, "symbolic-ref", "--short", "HEAD", required=False) or "detached",
            "input_digest": digest(files), "files": files, "unknowns": unknowns}


def _inventory(root: Path) -> dict[str, Any]:
    snapshot = _snapshot(root)
    names = [entry["path"] for entry in snapshot["files"] if entry.get("state") != "deleted"]
    build_names = {"pyproject.toml", "setup.py", "package.json", "pom.xml", "build.gradle", "Makefile", "Cargo.toml", "go.mod", "requirements.txt"}
    build = [path for path in names if Path(path).name in build_names]
    tests = [path for path in names if any(part in {"test", "tests", "__tests__"} for part in Path(path).parts)
             or Path(path).name.startswith("test_") or ".test." in Path(path).name or ".spec." in Path(path).name]
    docs = [path for path in names if Path(path).suffix.lower() in {".md", ".rst"}]
    candidates = []
    for path in names:
        lower = path.lower()
        kind = None
        if any(token in lower for token in ("openapi", "swagger")):
            kind = "api"
        elif lower.endswith(".proto"):
            kind = "rpc"
        elif any(part in {"contracts", "schemas", "events"} for part in Path(lower).parts):
            kind = "contract_or_data"
        if kind:
            candidates.append({"candidate_id": "candidate-" + digest(path).split(":")[-1][:12], "kind": kind,
                               "paths": [path], "confirmation_state": "unconfirmed",
                               "source_ref": {"storage": "local_snapshot", "base_commit": snapshot["base_commit"],
                                              "path": path, "content_digest": next(item["content_digest"] for item in snapshot["files"] if item["path"] == path)},
                               "consumers": [], "limitations": "filename evidence only; semantics and consumers unknown"})
    baseline = load(safe(root, ".specify/knowledge/baseline.json"), {})
    return {"snapshot": snapshot, "baseline_record": baseline or None, "dimensions": {
        "business_and_function": {"source_paths": docs, "state": "needs_semantic_review"},
        "internal_architecture": {"top_level_paths": sorted({Path(path).parts[0] for path in names}), "state": "needs_semantic_review"},
        "external_boundaries": {"candidates": candidates, "state": "needs_confirmation"},
        "build_and_run": {"source_paths": build, "execution_state": "not_run"},
        "selftests": {"source_paths": tests, "execution_state": "not_run", "coverage": "unknown",
                      "historical_baseline": {k: baseline.get(k) for k in ("record_path", "created_at", "execution_state", "evidence_verdict")} if baseline else None},
        "version_and_recovery": {"base_commit": snapshot["base_commit"], "branch": snapshot["branch"], "production_state": "unknown", "recovery_state": "unknown"},
        "knowledge_and_issues": {"source_paths": docs, "unknowns": snapshot["unknowns"], "history_completeness": "unknown"}},
        "limitations": ["Inventory locates evidence; it does not infer business intent or prove exhaustive dependencies.",
                        "Discovered build and test files have not been executed."]}


def inspect_project(args: argparse.Namespace) -> dict[str, Any]:
    root = _root(args)
    return {"ok": True, "inventory": _inventory(root)}


def _main_branch(root, explicit=None):
    if explicit:
        return explicit
    remote = _git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", required=False)
    if remote:
        return remote
    current = _git(root, "symbolic-ref", "--short", "HEAD", required=False)
    for branch in ("main", "master"):
        if current == branch or _git(root, "rev-parse", "--verify", "refs/heads/" + branch, required=False):
            return branch
    raise ValueError("Cannot infer the main branch; provide --main-branch explicitly")


def init_project(args: argparse.Namespace) -> dict[str, Any]:
    root = _root(args)
    path = safe(root, ".specify/project.yaml")
    config = load(path, default=None)
    if config is None:
        if not getattr(args, "project_id", None):
            raise ValueError("--project-id is required for a new project")
        identifier(args.project_id)
        config = {"schema_version": SCHEMA, "protocol_version": "0.1-draft", "project_id": args.project_id,
                  "name": args.project_id, "main_branch": _main_branch(root, getattr(args, "main_branch", None)),
                  "release_records": [], "selftest_entries": [], "resource_budget": {"max_seconds": None}}
        save(path, config)
    elif getattr(args, "project_id", None) and config.get("project_id") != args.project_id:
        raise ValueError("existing project identity differs; explicit migration required")
    _config(root)
    local_ignore = safe(root, ".specify/local/.gitignore")
    if not local_ignore.exists():
        local_ignore.parent.mkdir(parents=True, exist_ok=True)
        local_ignore.write_text("*\n!.gitignore\n", encoding="utf-8")
    workspace = safe(root, ".specify/local/workspace.json")
    if not workspace.exists():
        save(workspace, {"projects": {config["project_id"]: str(root)}})
    result = refresh_knowledge(args)
    result["initialized"] = True
    result["selftest_execution_state"] = "not_run"
    return result


def refresh_knowledge(args: argparse.Namespace) -> dict[str, Any]:
    root = _root(args)
    config = _config(root)
    inventory = _inventory(root)
    snapshot = inventory["snapshot"]
    current_path = safe(root, ".specify/knowledge/current.md")
    previous_meta, previous_body = ({}, "")
    if current_path.exists():
        previous_meta, previous_body = read_record(current_path)
        if previous_meta.get("project_id") != config["project_id"]:
            raise ValueError("current knowledge belongs to another project")
    if AUTO_START in previous_body or AUTO_END in previous_body:
        if previous_body.count(AUTO_START) != 1 or previous_body.count(AUTO_END) != 1 or previous_body.index(AUTO_START) > previous_body.index(AUTO_END):
            raise ValueError("invalid generated knowledge markers; previous knowledge preserved")
        manual = re.sub(re.escape(AUTO_START) + r".*?" + re.escape(AUTO_END), "", previous_body, flags=re.S).strip()
    else:
        manual = previous_body.strip()
    boundary_path = safe(root, ".specify/knowledge/boundaries/index.yaml")
    boundaries = load(boundary_path, default={"schema_version": SCHEMA, "boundaries": []})
    if not isinstance(boundaries, dict) or not isinstance(boundaries.get("boundaries"), list):
        raise ValueError("invalid boundary index; previous knowledge preserved")
    for boundary in boundaries["boundaries"]:
        if not isinstance(boundary, dict) or not boundary.get("contract_id"):
            raise ValueError("each curated boundary requires contract_id")
        identifier(boundary["contract_id"])
        for relative in boundary.get("paths", []):
            if not _allowed(relative):
                raise ValueError("boundary path targets excluded sensitive material")
            safe(root, relative)
    old_candidates = {entry.get("candidate_id"): entry for entry in boundaries.get("candidates", []) if isinstance(entry, dict)}
    candidates = inventory["dimensions"]["external_boundaries"]["candidates"]
    new_ids = {entry["candidate_id"] for entry in candidates}
    for candidate_id, candidate in old_candidates.items():
        if candidate_id not in new_ids:
            candidate = dict(candidate, observation_state="not_observed", review_required=True)
            candidates.append(candidate)
    boundaries["candidates"] = candidates
    boundaries["unknowns"] = boundaries.get("unknowns", [])
    boundaries["observed_input_digest"] = snapshot["input_digest"]
    meta = {"schema_version": SCHEMA, "record_type": "project_knowledge", "project_id": config["project_id"],
            "branch": snapshot["branch"], "base_commit": snapshot["base_commit"], "input_digest": snapshot["input_digest"],
            "source_set_digest": digest(snapshot["files"]), "refreshed_at": now(),
            "production_baselines": production_baselines(root), "production_state": "per_environment_authority",
            "unknowns": snapshot["unknowns"]}
    observed = AUTO_START + "\n## Observed working candidate\n\n```json\n" + json.dumps(inventory["dimensions"], ensure_ascii=False, indent=2) + "\n```\n\nCurrent production is unknown unless an authoritative environment record establishes it.\n" + AUTO_END
    if not manual:
        manual = "# Project knowledge\n\n## Human constraints and unresolved issues\n\nNo business intent or architecture approval has been inferred by inventory."
    if current_path.exists():
        history_id = digest({"meta": previous_meta, "body": previous_body}).split(":")[-1]
        history_path = safe(root, ".specify/knowledge/history/" + history_id + ".md")
        if not history_path.exists():
            write_record(history_path, previous_meta, previous_body)
    meta["boundary_index_digest"] = digest(boundaries)
    save(boundary_path, boundaries)
    write_record(current_path, meta, manual + "\n\n" + observed + "\n")
    return {"ok": True, "project_id": config["project_id"], "knowledge_path": ".specify/knowledge/current.md",
            "input_digest": snapshot["input_digest"], "boundary_candidates": len(candidates), "unknowns": snapshot["unknowns"],
            "selftests": inventory["dimensions"]["selftests"]}


def check_knowledge(args: argparse.Namespace) -> dict[str, Any]:
    root = _root(args)
    config = _config(root)
    path = safe(root, ".specify/knowledge/current.md")
    if not path.exists():
        return {"ok": False, "errors": ["current knowledge is missing"]}
    meta, _ = read_record(path)
    snapshot = _snapshot(root)
    errors = []
    if meta.get("project_id") != config["project_id"]:
        errors.append("knowledge project identity mismatch")
    if meta.get("input_digest") != snapshot["input_digest"]:
        errors.append("working inputs changed since knowledge refresh")
    if meta.get("branch") != snapshot["branch"]:
        errors.append("knowledge applies to a different branch")
    boundaries = load(safe(root, ".specify/knowledge/boundaries/index.yaml"), default=None)
    if boundaries is None or meta.get("boundary_index_digest") != digest(boundaries):
        errors.append("boundary index changed without knowledge refresh")
    if snapshot["unknowns"]:
        errors.append("inventory has unresolved coverage gaps")
    return {"ok": not errors, "errors": errors, "unknowns": snapshot["unknowns"]}


def _repositories(root: Path) -> dict[str, Path]:
    config = _config(root)
    workspace = load(safe(root, ".specify/local/workspace.json"), default={"projects": {}})
    mapping = workspace.get("projects", {})
    if not isinstance(mapping, dict):
        raise ValueError("workspace.projects must be a project_id to local path mapping")
    projects = {config["project_id"]: root}
    for project_id, raw in mapping.items():
        identifier(project_id)
        if not isinstance(raw, str) or not Path(raw).is_absolute():
            raise ValueError("workspace paths must be absolute local paths")
        path = Path(raw)
        if path.is_symlink():
            raise ValueError("workspace repository root must not be a symlink")
        path = path.resolve()
        if not path.is_dir() or Path(_git(path, "rev-parse", "--show-toplevel")).resolve() != path.resolve():
            raise ValueError("registered repository unavailable or not a repository root: " + project_id)
        actual = _config(path)
        if actual["project_id"] != project_id:
            raise ValueError("registered repository identity mismatch: " + project_id)
        if project_id in projects and projects[project_id] != path.resolve():
            raise ValueError("duplicate project identity: " + project_id)
        projects[project_id] = path.resolve()
    return projects


def _resolve_source(source: dict[str, Any], projects: dict[str, Path]) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise ValueError("source must be an object")
    project_id = source.get("project_id")
    if project_id not in projects:
        raise ValueError("source project is not registered: " + str(project_id))
    relative = source.get("path", "")
    if not relative or not _allowed(relative):
        raise ValueError("source path missing or excluded")
    safe(projects[project_id], relative)
    ref = source.get("ref")
    if not isinstance(ref, str) or not ref or ref.startswith("-") or "\n" in ref:
        raise ValueError("Git source requires an explicit ref")
    commit = _git(projects[project_id], "rev-parse", "--verify", ref + "^{commit}")
    tree = _git(projects[project_id], "ls-tree", commit, "--", relative)
    if tree.startswith("120000 "):
        raise ValueError("Git source must not be a symlink")
    if not tree or " blob " not in tree.split("\t", 1)[0]:
        raise ValueError("Git source must identify a regular file")
    result = subprocess.run(["git", "-C", str(projects[project_id]), "show", commit + ":" + relative], capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError("source is unavailable at recorded Git ref: " + relative)
    import hashlib
    content_digest = "sha256:" + hashlib.sha256(result.stdout).hexdigest()
    if source.get("content_digest") and source["content_digest"] != content_digest:
        raise ValueError("source content digest mismatch: " + relative)
    return dict(source, storage="git", ref=commit, observed_ref=source.get("observed_ref", ref), resolved_commit=commit, content_digest=content_digest)


def _feature(root: Path, args: argparse.Namespace) -> Path:
    path = safe(root, args.feature_dir)
    if path == root or not path.is_dir():
        raise ValueError("--feature-dir must identify an existing project feature directory")
    return path


def exchange_snapshot(root, context):
    """Observe relevant notices at a gate without adopting any new dependency."""
    from .exchange import scan
    result = scan(root, context)
    changes = [{key: item.get(key) for key in ("producer_project", "change_id", "semantic_digest", "target_release", "contract_ids")}
               for item in result["changes"]]
    changes.sort(key=lambda item: (item["producer_project"], item["change_id"]))
    errors = sorted(result["errors"], key=lambda item: json.dumps(item, sort_keys=True))
    value = {"changes": changes, "errors": errors}
    return dict(value, digest=digest(value))


def build_context(args: argparse.Namespace) -> dict[str, Any]:
    root = _root(args)
    config = _config(root)
    feature = _feature(root, args)
    knowledge = check_knowledge(args)
    if not knowledge["ok"]:
        return {"ok": False, "errors": ["refresh or resolve project knowledge before context build"] + knowledge["errors"]}
    existing = load(feature / "context-lock.json", {})
    inputs = load(safe(root, args.inputs), default={}) if getattr(args, "inputs", None) else {k: existing[k] for k in ("sources", "target_dependency_set", "unknowns") if k in existing}
    if not isinstance(inputs, dict):
        raise ValueError("context inputs must be an object")
    projects = _repositories(root)
    sources = [_resolve_source(source, projects) for source in inputs.get("sources", [])]
    targets = inputs.get("target_dependency_set", {})
    if not isinstance(targets, dict):
        raise ValueError("target_dependency_set must map project_id to target selection")
    resolved_targets = {}
    for project_id, target in targets.items():
        identifier(project_id)
        if not isinstance(target, dict) or target.get("basis_kind") not in {"implementation", "release", "design_confirmed", "confirmed_design"}:
            raise ValueError("target dependency requires an explicit basis_kind")
        if target.get("basis_ref", {}).get("project_id") != project_id:
            raise ValueError("target project must match its basis reference")
        source = _resolve_source(target.get("basis_ref", {}), projects)
        resolved = dict(target, basis_ref=source)
        if target.get("basis_kind") in {"design_confirmed", "confirmed_design"}:
            confirmation = target.get("consumer_confirmation_ref")
            if not isinstance(confirmation, dict) or confirmation.get("project_id") != config["project_id"]:
                raise ValueError("design target requires this consumer's explicit confirmation reference")
            resolved["consumer_confirmation_ref"] = _resolve_source(confirmation, projects)
            cref = resolved["consumer_confirmation_ref"]
            decision_data = parse(_git(projects[config["project_id"]], "show", cref["resolved_commit"] + ":" + cref["path"]))
            decisions = decision_data.get("decisions", [decision_data])
            valid = any(d.get("scope") == "external_design" and d.get("accepted") is True and d.get("actor") and d.get("source") and d.get("reason") and d.get("artifact_digest") == source["content_digest"] and not d.get("example") for d in decisions)
            if not valid:
                raise ValueError("consumer confirmation is not bound to the adopted external design")
            resolved["availability"] = "design_only_not_implemented_or_deployed"
            resolved["confirmation_verdict"] = "bound_decision_recorded"
        resolved_targets[project_id] = resolved
    local_paths = [".specify/project.yaml", ".specify/knowledge/current.md", ".specify/knowledge/boundaries/index.yaml", ".specify/memory/constitution.md"]
    for name in ("spec.md", "plan.md", "us-design.md", "compatibility.md"):
        path = feature / name
        if path.exists():
            local_paths.append(str(path.relative_to(root)))
    local_sources = [{"path": relative, "content_digest": file_digest(safe(root, relative))}
                     for relative in local_paths if safe(root, relative).is_file()]
    snapshot = _snapshot(root)
    lock = {"schema_version": SCHEMA, "project_id": config["project_id"], "feature_id": feature.name,
            "created_at": now(), "local_snapshot": snapshot, "local_sources": local_sources,
            "sources": sources, "target_dependency_set": resolved_targets,
            "production_baselines": production_baselines(root), "production_state": "per_environment_authority",
            "unknowns": inputs.get("unknowns", []) + snapshot["unknowns"]}
    lock["exchange_snapshot"] = exchange_snapshot(root, lock)
    lock["context_digest"] = digest({key: value for key, value in lock.items() if key != "created_at"})
    save(feature / "context-lock.json", lock)
    return {"ok": True, "context_path": str((feature / "context-lock.json").relative_to(root)),
            "context_digest": lock["context_digest"], "unknowns": lock["unknowns"], "exchange_snapshot": lock["exchange_snapshot"]}


def check_context(args: argparse.Namespace) -> dict[str, Any]:
    root = _root(args)
    config = _config(root)
    feature = _feature(root, args)
    lock = load(feature / "context-lock.json", default=None)
    if not isinstance(lock, dict):
        return {"ok": False, "errors": ["context lock is missing"]}
    errors, observations = [], []
    if lock.get("schema_version") != SCHEMA or lock.get("project_id") != config["project_id"]:
        errors.append("context schema or project identity mismatch")
    expected = digest({key: value for key, value in lock.items() if key not in {"created_at", "context_digest"}})
    if lock.get("context_digest") != expected:
        errors.append("context lock content was changed without rebuilding")
    if lock.get("production_baselines", []) != production_baselines(root):
        errors.append("authoritative release state changed; rebuild and reassess context")
    current_exchange = exchange_snapshot(root, lock)
    if lock.get("exchange_snapshot") != current_exchange:
        errors.append("relevant external notices or scan gaps changed; rebuild and reassess context")
    snapshot = _snapshot(root)
    if lock.get("local_snapshot", {}).get("input_digest") != snapshot["input_digest"]:
        (observations if getattr(args, "allow_local_changes", False) else errors).append("project working inputs changed")
    if lock.get("local_snapshot", {}).get("branch") != snapshot["branch"]:
        errors.append("project branch changed")
    for source in lock.get("local_sources", []):
        path = safe(root, source["path"])
        if not path.is_file() or file_digest(path) != source["content_digest"]:
            errors.append("local context source changed: " + source["path"])
    projects = _repositories(root)
    all_sources = list(lock.get("sources", []))
    for target in lock.get("target_dependency_set", {}).values():
        all_sources.append(target["basis_ref"])
        if target.get("consumer_confirmation_ref"):
            all_sources.append(target["consumer_confirmation_ref"])
    for source in all_sources:
        try:
            _resolve_source(source, projects)
            observed = dict(source, ref=source.get("observed_ref", source["ref"]))
            refreshed = _resolve_source(observed, projects)
            if refreshed["resolved_commit"] != source["resolved_commit"]:
                observations.append("source ref moved with unchanged selected content: " + source["path"])
        except (ValueError, KeyError) as exc:
            errors.append(str(exc))
    if snapshot["unknowns"]:
        errors.append("inventory has unresolved coverage gaps")
    return {"ok": not errors, "errors": errors, "observations": observations, "unknowns": lock.get("unknowns", []), "exchange_snapshot": current_exchange}


def register(subparsers: Any) -> None:
    project = subparsers.add_parser("project", help="Inspect or initialize local project facts")
    project_sub = project.add_subparsers(dest="project_action", required=True)
    inspect = project_sub.add_parser("inspect")
    inspect.set_defaults(handler=inspect_project)
    init = project_sub.add_parser("init")
    init.add_argument("--project-id")
    init.add_argument("--main-branch")
    init.set_defaults(handler=init_project)
    baseline = project_sub.add_parser("baseline")
    baseline.add_argument("--feature-dir", default="specs/_baseline")
    baseline.add_argument("--catalog", default=".specify/selftests/catalog.yaml")
    baseline.set_defaults(handler=baseline_project)
    knowledge = subparsers.add_parser("knowledge", help="Refresh or verify project knowledge")
    knowledge_sub = knowledge.add_subparsers(dest="knowledge_action", required=True)
    knowledge_sub.add_parser("refresh").set_defaults(handler=refresh_knowledge)
    knowledge_sub.add_parser("check").set_defaults(handler=check_knowledge)
    context = subparsers.add_parser("context", help="Build or verify version-bound feature context")
    context_sub = context.add_subparsers(dest="context_action", required=True)
    for name, handler in (("build", build_context), ("check", check_context)):
        command = context_sub.add_parser(name)
        command.add_argument("--feature-dir", required=True)
        if name == "build":
            command.add_argument("--inputs", help="Repository-relative JSON file with selected Git sources and target dependencies")
        else:
            command.add_argument("--allow-local-changes", action="store_true", help="Report expected implementation changes; external and source drift still fail")
        command.set_defaults(handler=handler)
