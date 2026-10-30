"""Local, version-pinned project exchange. No network or cross-project writes."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

from .common import load, save, safe, digest, file_digest, now, identifier, read_record, write_record, parse, dependency_digest

PROTOCOL = "0.1-draft"
STATES = {"design_confirmed", "implemented", "merged", "withdrawn"}
RECEIPTS = {"not_assessed", "unaffected", "adaptation_required", "adapting", "verified", "deferred", "blocked"}
INDEX = ".specify/exchange/index.json"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _id(value):
    _require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value) is not None, "invalid identifier")
    return value


def _path(root, relative):
    _require(isinstance(relative, str) and relative and "\\" not in relative, "invalid relative path")
    p = PurePosixPath(relative)
    _require(not p.is_absolute() and not any(x in (".", "..") for x in relative.split("/")), "path escapes project")
    _require(not re.match(r"^[A-Za-z]:", relative), "absolute path is forbidden")
    _require(not (set(p.parts) & {".git", ".ssh", ".aws", ".kube", ".credentials"}) and not p.name.startswith(".env") and p.name not in {"credentials", "credentials.json", "auth.json", ".netrc", ".npmrc", "secrets.json", "secrets.yaml", "id_rsa", "id_ed25519"} and p.suffix.lower() not in {".pem", ".key", ".p12", ".pfx"}, "sensitive material is outside the exchange boundary")
    root = Path(root).resolve()
    current = root
    for part in p.parts:
        current = current / part
        _require(not current.is_symlink(), "symlink path is forbidden: " + relative)
    result = Path(safe(root, relative))
    _require(result.resolve().is_relative_to(root) if hasattr(Path, "is_relative_to") else str(result.resolve()).startswith(str(root) + "/"), "path escapes project")
    return result


def _sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _hash(value):
    _require(isinstance(value, str), "content_digest is required")
    raw = value[7:] if value.startswith("sha256:") else value
    _require(re.fullmatch(r"[0-9a-f]{64}", raw) is not None, "invalid SHA-256 digest")
    return "sha256:" + raw


def _json_bytes(data):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result
    try:
        return parse(data.decode("utf-8") if isinstance(data, bytes) else data)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON: " + str(exc))


def _record_bytes(data):
    text = data.decode("utf-8") if isinstance(data, bytes) else data
    _require(text.startswith("---\n") or text.startswith("---\r\n"), "JSON frontmatter is required")
    lines = text.splitlines()
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise ValueError("unterminated frontmatter")
    meta = _json_bytes("\n".join(lines[1:end]))
    _require(isinstance(meta, dict), "frontmatter must be an object")
    return meta, "\n".join(lines[end + 1:])


def _git(root, *args):
    result = subprocess.run(["git", "-C", str(root)] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _require(result.returncode == 0, "Git reference unavailable: " + result.stderr.decode("utf-8", "replace").strip()[:300])
    return result.stdout


def _commit(root, ref):
    _require(isinstance(ref, str) and ref and not ref.startswith("-") and not any(ord(c) < 32 for c in ref), "invalid Git ref")
    return _git(root, "rev-parse", "--verify", ref + "^{commit}").decode().strip()


def _blob(root, commit, relative):
    _path(root, relative)  # also reject a working-tree symlink at the requested path
    parts = PurePosixPath(relative).parts
    final_oid = None
    for end in range(1, len(parts) + 1):
        name = "/".join(parts[:end])
        row = _git(root, "ls-tree", "-z", commit, "--", name)
        _require(bool(row), "Git path unavailable: " + name)
        header, returned = row.rstrip(b"\0").split(b"\t", 1)
        mode, kind, oid = header.decode().split()
        _require(returned.decode() == name, "ambiguous Git path")
        if end < len(parts):
            _require(mode == "040000" and kind == "tree", "Git path crosses symlink/submodule")
        else:
            _require(mode in ("100644", "100755") and kind == "blob", "Git reference must identify a regular file")
            final_oid = oid
    return _git(root, "cat-file", "blob", final_oid)


def _config(root):
    value = _json_bytes(_path(root, ".specify/project.yaml").read_bytes())
    _require(isinstance(value, dict), "project configuration must be an object")
    _id(value.get("project_id"))
    return value


def workspace(root):
    """Return registered roots and discovery errors; never silently omit a project."""
    root = Path(root).resolve()
    own = _config(root)["project_id"]
    p = _path(root, ".specify/local/workspace.json")
    raw = _json_bytes(p.read_bytes()) if p.exists() else {"projects": {}}
    _require(isinstance(raw.get("projects"), dict), "workspace.projects must be an object")
    projects, errors = {own: root}, []
    roots = {str(root): own}
    for pid, name in raw["projects"].items():
        try:
            _id(pid)
            _require(isinstance(name, str) and Path(name).is_absolute(), "workspace roots must be absolute local paths")
            candidate = Path(name)
            _require(not candidate.is_symlink(), "workspace root must not be a symlink")
            candidate = candidate.resolve()
            _require(candidate.is_dir(), "workspace root unavailable")
            _require(_config(candidate)["project_id"] == pid, "workspace/project identity mismatch")
            _require(pid != own or candidate == root, "duplicate own project identity")
            _require(str(candidate) not in roots or roots[str(candidate)] == pid, "duplicate repository registration")
            _require(Path(_git(candidate, "rev-parse", "--show-toplevel").decode().strip()).resolve() == candidate, "workspace must identify repository root")
            projects[pid] = candidate
            roots[str(candidate)] = pid
        except (ValueError, OSError) as exc:
            errors.append({"project_id": pid, "status": "unresolved", "reason": str(exc)})
    return projects, errors


def validate_reference(root, reference, workspace=None, pin=False):
    """Resolve only registered local Git blobs; local snapshots are explicitly unverified."""
    _require(isinstance(reference, dict), "structured reference required")
    projects = workspace if workspace is not None else globals()["workspace"](root)[0]
    pid = _id(reference.get("project_id"))
    _require(pid in projects, "unregistered or unavailable project: " + pid)
    kind = reference.get("kind")
    _require(kind in {"code", "contract", "design", "decision", "evidence", "release_record", "handoff"}, "invalid reference kind")
    if reference.get("storage", "git") == "local_snapshot":
        _require(pid == _config(root)["project_id"], "foreign local snapshots are unavailable")
        _require(reference.get("visibility") == "local_only", "local snapshot requires local_only visibility")
        _id(reference.get("snapshot_id"))
        _hash(reference.get("input_digest"))
        _commit(projects[pid], reference.get("base_commit"))
        return {"status": "local_only", "available": False, "reference": dict(reference)}
    _require(reference.get("storage", "git") == "git", "unsupported reference storage")
    repo = projects[pid]
    sha = _commit(repo, reference.get("ref"))
    if reference.get("resolved_commit"):
        _require(reference["resolved_commit"] == sha, "Git ref moved from its recorded commit")
    if not pin:
        _require(reference.get("ref") == sha or reference.get("resolved_commit") == sha, "Git reference is not pinned to a commit")
    content = _blob(repo, sha, reference.get("path"))
    _require(_sha(content) == _hash(reference.get("content_digest")), "Git blob digest mismatch: " + reference["path"])
    normalized = dict(reference, ref=sha, resolved_commit=sha, content_digest=_sha(content))
    return {"status": "verified_reference", "available": True, "reference": normalized, "content": content}


def _refs(root, value, projects, pin=False):
    """Validate all structured refs without executing or interpreting their prose."""
    if isinstance(value, dict):
        if "project_id" in value and "kind" in value and ("path" in value or value.get("storage") == "local_snapshot"):
            checked = validate_reference(root, value, projects, pin)
            return checked["reference"]
        return {key: _refs(root, child, projects, pin) for key, child in value.items()}
    if isinstance(value, list):
        return [_refs(root, child, projects, pin) for child in value]
    return value


def _real(value):
    if isinstance(value, dict):
        _require(not value.get("example") and not value.get("synthetic_example") and not str(value.get("evidence_kind", "")).startswith("synthetic") and value.get("evidence_mode") != "synthetic_example", "synthetic/example records are not admissible")
        for child in value.values():
            _real(child)
    elif isinstance(value, list):
        for child in value:
            _real(child)


def _decision(root, refs, projects, purpose, subject=None, artifact_digest=None):
    """Acceptance is supported by a versioned structured decision, not a boolean claim."""
    for reference in refs:
        if reference.get("kind") != "decision":
            continue
        checked = validate_reference(root, reference, projects)
        if not checked["available"]:
            continue
        try:
            data = _json_bytes(checked["content"])
        except ValueError:
            continue
        _real(data)
        records = data.get("decisions", [data]) if isinstance(data, dict) else data
        for record in records if isinstance(records, list) else []:
            if not isinstance(record, dict):
                continue
            if record.get("kind", record.get("type", record.get("scope"))) != purpose:
                continue
            if (record.get("status") not in ("accepted", "confirmed", "approved") and record.get("accepted") is not True) or not record.get("reason") or not record.get("source"):
                continue
            if subject and record.get("change_id") != subject:
                continue
            if artifact_digest and record.get("artifact_digest") != artifact_digest:
                continue
            if record.get("actor") or record.get("confirmed_by"):
                return True
    return False


def _evidence_pass(root, meta, projects):
    required = meta.get("verified_case_ids")
    _require(required is None or isinstance(required, list) and required, "verified_case_ids must be a nonempty list")
    for reference in meta.get("evidence_refs", []):
        if reference.get("kind") != "evidence" or reference.get("project_id") != meta["consumer_project"]:
            continue
        checked = validate_reference(root, reference, projects)
        try:
            run = _json_bytes(checked["content"])
        except ValueError:
            continue
        _real(run)
        if not isinstance(run, dict) or run.get("project_id") != meta["consumer_project"] or run.get("execution_state") != "complete":
            continue
        planned = run.get("planned_case_ids", [])
        results = run.get("case_results", [])
        if isinstance(results, dict):
            results = [dict(v, case_id=k) if isinstance(v, dict) else {"case_id": k, "status": v} for k, v in results.items()]
        if not isinstance(results, list) or not planned or len(set(planned)) != len(planned):
            continue
        actual = {item.get("case_id"): item.get("status") for item in results if isinstance(item, dict)}
        if len(actual) != len(results) or set(actual) != set(planned) or any(s not in ("pass", "fail") for s in actual.values()):
            continue
        wanted = required if required is not None else planned
        if not set(wanted).issubset(actual) or any(actual[k] != "pass" for k in wanted):
            continue
        failures = any(status == "fail" for status in actual.values())
        if failures:
            if not required or not _decision(root, meta.get("decision_refs", []), projects, "risk_acceptance", meta["change_id"]):
                continue
        elif run.get("evidence_verdict") != "pass":
            continue
        _require(bool(run.get("input_snapshot")), "selftest evidence lacks input snapshot")
        _require(run["input_snapshot"].get("dependency_digest") == dependency_digest(meta["target_dependency_set"]), "selftest evidence targets a different dependency combination")
        _require(bool(run.get("commands")), "selftest evidence lacks collected command outputs")
        from .evidence import validate_collected
        cat = run.get("catalog_snapshot", {})
        problems = validate_collected(run, cat.get("cases", []), lambda path: _blob(projects[meta["consumer_project"]], checked["reference"]["ref"], path))
        _require(not problems, "shared execution evidence invalid: " + "; ".join(problems))
        _require(meta.get("feature_id") == run.get("feature_id") and bool(meta.get("feature_id")), "verified receipt must identify its tested consumer feature")
        return True
    return False


def _validate(root, meta, projects, pin=False):
    _require(isinstance(meta, dict), "record must be an object")
    _real(meta)
    _require(meta.get("protocol_version") == PROTOCOL, "unsupported protocol version")
    _require(type(meta.get("revision")) is int and meta["revision"] > 0, "revision must be a positive integer")
    typ = meta.get("record_type")
    _require(typ in ("handoff", "receipt"), "unsupported record_type")
    pid = _id(meta.get("producer_project"))
    change = _id(meta.get("change_id"))
    _require(change.startswith(pid + "."), "change_id must carry producer namespace")
    result = _refs(root, meta, projects, pin)
    if typ == "handoff":
        for field in ("feature_id", "development_state", "baseline_release", "target_release", "design_ref", "contract_changes", "required_consumers", "unknown_dependencies", "compatibility_ref", "evidence_refs", "origin_chain", "created_at", "supersedes", "summary", "rationale"):
            _require(field in result, "handoff missing " + field)
        _require(result["summary"] and result["rationale"], "handoff needs change summary and rationale")
        _id(result["feature_id"])
        _require(result["development_state"] in STATES, "invalid development_state")
        _require(result.get("previous_revision") == (None if result["revision"] == 1 else result["revision"] - 1), "previous_revision must match preceding revision")
        _require(isinstance(result["design_ref"], dict) and result["design_ref"].get("kind") == "design", "design_ref is required")
        _require(isinstance(result["compatibility_ref"], dict), "compatibility_ref is required")
        _require(isinstance(result["contract_changes"], list), "contract_changes must be a list")
        _require(result["contract_changes"] or result.get("no_external_change_reason"), "empty contract_changes needs an explicit no_external_change_reason")
        _require(result["design_ref"].get("project_id") == pid, "producer design must belong to producer")
        _require(result["compatibility_ref"].get("project_id") == pid and result["compatibility_ref"].get("kind") == "design", "producer compatibility design required")
        seen = set()
        for contract in result["contract_changes"]:
            cid = _id(contract.get("contract_id"))
            _require(cid not in seen, "duplicate contract_id")
            seen.add(cid)
            _require(contract.get("before") or contract.get("after"), "contract must have before or after source")
            for side in ("before", "after"):
                if contract.get(side):
                    _require(contract[side].get("kind") == "contract" and contract[side].get("project_id") == pid, "contract source identity mismatch")
        consumers = set()
        for consumer in result["required_consumers"]:
            cid = _id(consumer.get("project_id"))
            _require(cid not in consumers and consumer.get("reason") and consumer.get("basis"), "invalid or duplicate required consumer")
            consumers.add(cid)
        impl = result.get("implementation_ref")
        if result["development_state"] in ("implemented", "merged"):
            _require(isinstance(impl, dict), "implementation_ref required after implementation")
        if impl and impl.get("storage") == "local_snapshot":
            _require(result.get("source_available_to_consumers") is False, "local snapshot must advertise unavailable source")
        if impl:
            _require(impl.get("project_id") == pid and impl.get("kind") == "code", "implementation reference identity mismatch")
        if result["development_state"] == "merged":
            _require(impl.get("storage", "git") == "git", "merged state requires shared Git source")
            main = _commit(projects[pid], _config(projects[pid]).get("main_branch", "main"))
            merged = subprocess.run(["git", "-C", str(projects[pid]), "merge-base", "--is-ancestor", impl["ref"], main], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _require(merged.returncode == 0, "implementation is not merged into configured main branch")
    else:
        for field in ("receipt_id", "consumer_project", "handoff_revision", "handoff_ref", "contract_assumptions", "target_dependency_set", "status", "recheck_required", "affected_features", "evidence_refs", "decision_refs", "reason", "observed_at"):
            _require(field in result, "receipt missing " + field)
        _id(result["receipt_id"])
        _id(result["consumer_project"])
        _require(result["status"] in RECEIPTS and type(result["recheck_required"]) is bool, "invalid receipt state")
        _require(bool(result["reason"]), "receipt requires a reason")
        _require(isinstance(result["target_dependency_set"], dict), "target_dependency_set must be an object")
        _require(all(r.get("project_id") == result["consumer_project"] for r in result["decision_refs"]), "consumer decisions must belong to consumer")
        expected = ".specify/exchange/outbox/{}/r{}.md".format(change, result["handoff_revision"])
        href = result["handoff_ref"]
        _require(href.get("project_id") == pid and href.get("path") == expected, "handoff_ref identity/path mismatch")
        source = validate_reference(root, href, projects)
        _require(source["available"], "handoff source unavailable")
        handoff, unused = _record_bytes(source["content"])
        _real(handoff)
        _require(handoff.get("change_id") == change and handoff.get("revision") == result["handoff_revision"] and handoff.get("producer_project") == pid, "handoff metadata mismatch")
        _validate(root, handoff, projects)
        contracts = {c["contract_id"]: _hash((c.get("after") or c["before"])["content_digest"]) for c in handoff["contract_changes"]}
        _require(isinstance(result["contract_assumptions"], list) and result["contract_assumptions"], "contract assumptions required")
        for assumption in result["contract_assumptions"]:
            _require(assumption.get("contract_id") in contracts and _hash(assumption.get("content_digest")) == contracts[assumption["contract_id"]], "contract assumption hash mismatch")
        if handoff["development_state"] == "design_confirmed" and result["status"] not in ("not_assessed", "blocked"):
            chosen = result["target_dependency_set"].get(pid, {})
            _require(chosen.get("basis_kind") in ("confirmed_design", "design_confirmed") and chosen.get("basis_ref") == handoff["design_ref"], "unmerged design must be explicitly selected by exact reference")
            _require(_decision(root, result["decision_refs"], projects, "external_design", artifact_digest=handoff["design_ref"]["content_digest"]), "design adoption requires content-bound consumer confirmation")
        if result["status"] == "unaffected":
            _require(any(ref.get("project_id") == result["consumer_project"] for ref in result.get("source_refs", []) + result["evidence_refs"]), "unaffected requires consumer-side source evidence")
            _require(_decision(root, result["decision_refs"], projects, "impact", change), "unaffected requires a scoped consumer impact decision")
        if result["status"] == "verified":
            _require(_evidence_pass(root, result, projects), "verified receipt requires complete real selftest evidence")
        if result["status"] == "deferred" and result.get("deferral", {}).get("accepted"):
            _require(result["deferral"].get("target_release") and result["deferral"].get("scope") and result["deferral"].get("reason"), "accepted deferral needs target, scope and reason")
            _require(_decision(root, result["decision_refs"], projects, "deferral", change), "accepted deferral lacks scoped decision evidence")
    return result


def _semantic(meta):
    """Only decision-relevant fields; timestamps and prose are not ordering keys."""
    contracts = [{"contract_id": c["contract_id"], "before": c.get("before"), "after": c.get("after"), "change_kind": c.get("change_kind"), "compatibility_assessment": c.get("compatibility_assessment")} for c in meta.get("contract_changes", [])]
    return digest({"contracts": contracts, "target_release": meta.get("target_release"), "design_ref": meta.get("design_ref"), "compatibility_ref": meta.get("compatibility_ref"), "withdrawn": meta.get("development_state") == "withdrawn", "support_window": meta.get("support_window"), "required_consumers": meta.get("required_consumers"), "unknown_dependencies": meta.get("unknown_dependencies")})


def _input(root, relative, body_path=None):
    path = _path(root, relative)
    if path.suffix.lower() == ".json":
        meta, body = _json_bytes(path.read_bytes()), ""
    else:
        meta, body = _record_bytes(path.read_bytes())
    if body_path:
        body = _path(root, body_path).read_text(encoding="utf-8")
    return meta, body


def publish(root, input_path, body_path=None, expected_type="handoff"):
    root = Path(root).resolve()
    projects, discovery = workspace(root)
    meta, body = _input(root, input_path, body_path)
    meta = _validate(root, meta, projects, pin=True)
    _require(meta["record_type"] == expected_type, "record type does not match command")
    own = _config(root)["project_id"]
    _require(meta["producer_project" if expected_type == "handoff" else "consumer_project"] == own, "only own-project records may be written")
    folder = "outbox/" + meta["change_id"] if expected_type == "handoff" else "receipts/{}/{}".format(meta["change_id"], own)
    relative = ".specify/exchange/{}/r{}.md".format(folder, meta["revision"])
    path = _path(root, relative)
    index_path = _path(root, INDEX)
    index = load(index_path, {"protocol_version": PROTOCOL, "project_id": own, "entries": []})
    _require(index.get("project_id") == own and index.get("protocol_version") == PROTOCOL and isinstance(index.get("entries"), list), "index identity/version mismatch")
    replay = path.exists()
    if path.exists():
        old, old_body = _record_bytes(path.read_bytes())
        _require(old == meta and old_body.strip() == body.strip(), "revision already exists with different content")
    if meta["revision"] > 1:
        previous = _path(root, ".specify/exchange/{}/r{}.md".format(folder, meta["revision"] - 1))
        _require(previous.is_file(), "previous revision is missing")
        prior, unused = _record_bytes(previous.read_bytes())
        _require(prior["change_id"] == meta["change_id"], "revision chain identity mismatch")
    if not replay:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_record(path, meta, body)
    actual, unused = _record_bytes(path.read_bytes())
    _require(actual == meta, "record write verification failed")
    entry = {"record_type": expected_type, "change_id": meta["change_id"], "revision": meta["revision"], "path": relative, "content_digest": file_digest(path), "contract_ids": [c["contract_id"] for c in meta.get("contract_changes", meta.get("contract_assumptions", []))]}
    if expected_type == "handoff":
        entry["development_state"] = meta["development_state"]
    else:
        entry["consumer_project"] = own
        entry["status"] = meta["status"]
    index["entries"] = [e for e in index["entries"] if e.get("path") != relative] + [entry]
    index["updated_at"] = now()
    save(index_path, index)
    return {"ok": True, "idempotent": replay, "path": relative, "content_digest": file_digest(path), "visibility": "local_only_until_committed_and_synced", "discovery_issues": discovery}


def release_assumptions_current(root, meta, projects):
    """Compare imported current events, including rollbacks, with receipt assumptions."""
    for assumption in meta.get("release_assumptions", []):
        pid = assumption.get("project_id")
        _require(pid in projects, "release assumption project unavailable")
        status = release_status(projects[pid], assumption.get("environment"))
        _require(status["current_confirmed"] and status["current"]["record_id"] == assumption.get("record_id"), "release assumption changed or is unknown: " + pid)


def contract_conflicts(repo, notice):
    latest = {}
    for meta, path in _records(repo, "handoff"):
        if meta["change_id"] not in latest or meta["revision"] > latest[meta["change_id"]]["revision"]:
            latest[meta["change_id"]] = meta
    own = {c["contract_id"]: (c.get("after") or c["before"])["content_digest"] for c in notice["contract_changes"]}
    conflicts = []
    for other in latest.values():
        if other["change_id"] == notice["change_id"] or other["development_state"] == "withdrawn" or other["target_release"] != notice["target_release"]:
            continue
        if other["change_id"] in notice.get("supersedes", []) or notice["change_id"] in other.get("supersedes", []):
            continue
        for c in other["contract_changes"]:
            if c["contract_id"] in own and own[c["contract_id"]] != (c.get("after") or c["before"])["content_digest"]:
                conflicts.append({"change_id": other["change_id"], "contract_id": c["contract_id"]})
    return conflicts


def _records(repo, typ):
    folder = _path(repo, ".specify/exchange/" + ("outbox" if typ == "handoff" else "receipts"))
    if not folder.exists():
        return []
    records = []
    for candidate in sorted(folder.rglob("r*.md")):
        p = _path(repo, candidate.relative_to(repo).as_posix())
        meta, body = _record_bytes(p.read_bytes())
        _require(meta.get("record_type") == typ, "record in wrong exchange directory")
        records.append((meta, p))
    return records


def check_record(root, path):
    root = Path(root).resolve(); projects, errors = workspace(root)
    meta, body = _input(root, path)
    checked = _validate(root, meta, projects)
    return {"ok": not errors, "record": checked, "errors": errors}


def receipt_target_current(receipt, projects, context=None):
    if context is None and receipt.get("feature_id"):
        feature = _id(receipt["feature_id"])
        path = _path(projects[receipt["consumer_project"]], "specs/" + feature + "/context-lock.json")
        _require(path.is_file(), "consumer feature context is unavailable")
        context = load(path)
    if context is not None:
        _require(dependency_digest(context.get("target_dependency_set", {})) == dependency_digest(receipt["target_dependency_set"]), "current target dependency set differs from receipt assumptions")


def closure(root, change_id):
    root = Path(root).resolve(); projects, discovery = workspace(root)
    producer = _config(root)["project_id"]
    notices = [m for m, p in _records(root, "handoff") if m.get("change_id") == change_id]
    _require(notices, "change not found")
    notice = max(notices, key=lambda m: m["revision"])
    _validate(root, notice, projects)
    details = []; ready = True; resolved = True; deferred = False
    for consumer in notice["required_consumers"]:
        pid = consumer["project_id"]
        item = {"project_id": pid, "status": "not_assessed", "valid": False}
        try:
            _require(pid in projects, "consumer repository unavailable")
            receipts = [m for m, p in _records(projects[pid], "receipt") if m.get("producer_project") == producer and m.get("change_id") == change_id and m.get("consumer_project") == pid]
            _require(receipts, "consumer has not provided a receipt")
            rec = max(receipts, key=lambda m: m["revision"])
            rec = _validate(root, rec, projects)
            old_ref = validate_reference(root, rec["handoff_ref"], projects)
            old, unused = _record_bytes(old_ref["content"])
            _require(_semantic(old) == _semantic(notice), "related contract or compatibility assumptions changed")
            _require(not rec["recheck_required"], "consumer has flagged reassessment")
            release_assumptions_current(root, rec, projects)
            receipt_target_current(rec, projects)
            # Compare explicitly selected moving target refs against their pinned content.
            for target in rec["target_dependency_set"].values():
                if isinstance(target, dict) and target.get("basis_ref"):
                    validate_reference(root, target["basis_ref"], projects)
            item.update(status=rec["status"], valid=True, revision=rec["revision"],
                        feature_id=rec.get("feature_id"), target_dependency_set=rec["target_dependency_set"])
            accepted_deferral = rec["status"] == "deferred" and rec.get("deferral", {}).get("accepted") is True
            item["accepted_deferral"] = accepted_deferral
            resolved = resolved and (rec["status"] in ("unaffected", "verified") or accepted_deferral)
            ready = ready and rec["status"] in ("unaffected", "verified")
            deferred = deferred or accepted_deferral
        except (ValueError, OSError, KeyError) as exc:
            item["reason"] = str(exc); ready = False; resolved = False
        details.append(item)
    conflicts = contract_conflicts(root, notice)
    if conflicts:
        resolved = False
    if notice.get("unknown_dependencies") or discovery or conflicts or notice["development_state"] == "withdrawn":
        ready = False
    if notice["development_state"] == "withdrawn":
        resolved = False
    return {"ok": True, "change_id": change_id, "revision": notice["revision"], "assessment_resolved": resolved,
            "has_accepted_deferral": deferred, "joint_compatibility_ready": ready,
            "scope": "identified_consumers_at_the_reported_dependency_sets_only", "consumers": details,
            "unknown_dependencies": notice["unknown_dependencies"], "discovery_issues": discovery,
            "release_authorized": False, "contract_conflicts": conflicts}


def scan(root, context=None):
    root = Path(root).resolve(); projects, errors = workspace(root)
    own = _config(root)["project_id"]
    index_path = _path(root, ".specify/knowledge/boundaries/index.yaml")
    boundaries = load(index_path, {"boundaries": []}).get("boundaries", [])
    ids = {b.get("contract_id") for b in boundaries}
    selected = context.get("target_dependency_set", {}) if context else {}
    changes = []; seen = set(); local_closures = []
    for pid, repo in projects.items():
        try:
            notices = _records(repo, "handoff")
            latest = {}
            for meta, path in notices:
                key = meta.get("change_id")
                if key not in latest or meta.get("revision", 0) > latest[key][0].get("revision", 0):
                    latest[key] = (meta, path)
            # The index is a cache; cross-check source files instead of trusting a cursor.
            idx = load(_path(repo, INDEX), {"entries": []})
            for entry in idx.get("entries", []):
                p = _path(repo, entry["path"])
                if not p.is_file() or file_digest(p) != entry.get("content_digest"):
                    errors.append({"project_id": pid, "reason": "index/source mismatch: " + entry["path"]})
            for meta, path in latest.values():
                key = (pid, meta["change_id"], meta["revision"])
                if key in seen:
                    continue
                seen.add(key)
                try:
                    checked = _validate(root, meta, projects)
                    _require(checked["producer_project"] == pid, "notice belongs to a different project")
                    if pid == own:
                        local_closures.append(closure(root, meta["change_id"]))
                        continue
                    relevant = own in {c["project_id"] for c in checked["required_consumers"]} or bool(ids & {c["contract_id"] for c in checked["contract_changes"]}) or pid in selected
                    if relevant:
                        own_receipts = [m for m, p in _records(root, "receipt") if m.get("producer_project") == pid and m.get("change_id") == meta["change_id"]]
                        recheck = True; reason = "not_assessed"
                        if own_receipts:
                            rec = max(own_receipts, key=lambda x: x["revision"])
                            rec = _validate(root, rec, projects)
                            release_assumptions_current(root, rec, projects)
                            old, unused = _record_bytes(validate_reference(root, rec["handoff_ref"], projects)["content"])
                            recheck = rec["recheck_required"] or _semantic(old) != _semantic(checked) or bool(contract_conflicts(repo, checked))
                            reason = "related_change" if recheck else rec["status"]
                            try:
                                receipt_target_current(rec, projects, context)
                            except ValueError as exc:
                                recheck = True; reason = str(exc)
                        changes.append({"producer_project": pid, "change_id": meta["change_id"], "revision": meta["revision"],
                                        "semantic_digest": _semantic(checked), "target_release": checked["target_release"],
                                        "contract_ids": [c["contract_id"] for c in checked["contract_changes"]],
                                        "development_state": meta["development_state"], "recheck_required": recheck,
                                        "reason": reason, "adoption": "explicit_target_required", "origin_chain": meta.get("origin_chain", [])})
                except (ValueError, KeyError, OSError) as exc:
                    errors.append({"project_id": pid, "change_id": meta.get("change_id"), "reason": str(exc)})
            # Missing exchange metadata is a knowledge gap, never implicit absence of changes.
            if pid != own and not notices:
                errors.append({"project_id": pid, "reason": "no producer handoff records; boundary impact unknown"})
        except (ValueError, OSError, KeyError) as exc:
            errors.append({"project_id": pid, "reason": str(exc)})
    return {"ok": not errors, "changes": changes, "closures": local_closures, "errors": errors,
            "traversal": "one bounded pass over registered repositories; origin chains retained, no automatic propagation writes"}


RELEASE_FIELDS = ("record_id", "project_id", "environment", "release_id", "commit", "action", "previous_record_id", "occurred_at")


def _release_chain(history, project_id, environment):
    if not history:
        return None
    records = {}
    for item in history:
        _require(all(k in item for k in RELEASE_FIELDS), "release history fields missing")
        rid = _id(item["record_id"])
        _require(rid not in records, "duplicate release history identity")
        _require(item["project_id"] == project_id and item["environment"] == environment, "release history identity mismatch")
        records[rid] = item
    roots = [rid for rid, item in records.items() if item["previous_record_id"] is None]
    _require(len(roots) == 1, "release history must have one root")
    children = {}
    for rid, item in records.items():
        previous = item["previous_record_id"]
        if previous is not None:
            _require(previous in records, "release history predecessor missing")
            _require(previous not in children, "release history forks at " + str(previous))
            children[previous] = rid
    visited = set(); current = roots[0]
    while current not in visited:
        visited.add(current)
        if current not in children:
            _require(len(visited) == len(records), "release history is disconnected or cyclic")
            return current
        current = children[current]
    raise ValueError("release history contains a cycle")


def record_release(root, entry):
    root = Path(root).resolve(); projects, errors = workspace(root); _real(entry)
    _require(all(k in entry for k in RELEASE_FIELDS), "release record fields missing")
    _require(entry["project_id"] == _config(root)["project_id"], "only own release facts may be recorded")
    _id(entry["record_id"]); _id(entry["environment"])
    _require(entry["action"] in ("publish", "rollback", "withdraw"), "unknown release action")
    source = validate_reference(root, entry["source_ref"], projects, pin=True)
    _require(source["available"] and entry["source_ref"].get("kind") == "release_record", "authoritative release source required")
    fact = _json_bytes(source["content"]); _real(fact)
    _require(all(fact.get(k) == entry[k] for k in RELEASE_FIELDS), "release input differs from its authority source")
    _require(_commit(root, entry["commit"]) == entry["commit"], "release commit must be fixed")
    authority = _config(root).get("release_authority", {}).get(entry["environment"])
    _require(isinstance(authority, dict), "configure release_authority for this environment")
    _require(authority.get("project_id") == entry["source_ref"]["project_id"] and authority.get("path") == entry["source_ref"]["path"], "release source is not the configured authority")
    previous = entry["previous_record_id"]
    folder = _path(root, ".specify/exchange/releases/" + entry["environment"])
    result = dict(entry, source_ref=source["reference"])
    target = _path(root, ".specify/exchange/releases/" + entry["environment"] + "/" + entry["record_id"] + ".json")
    if target.exists():
        _require(load(target) == result, "release record ID cannot be rewritten")
        return release_status(root, entry["environment"])
    history = [load(_path(root, p.relative_to(root).as_posix())) for p in sorted(folder.glob("*.json"))]
    tip = _release_chain(history, entry["project_id"], entry["environment"])
    _require(previous == tip, "release predecessor must be the current linear history tip")
    if target.exists():
        _require(load(target) == result, "release record ID cannot be rewritten")
    else:
        save(target, result)
    return release_status(root, entry["environment"])


def release_status(root, environment):
    root = Path(root).resolve(); _id(environment)
    projects, discovery = workspace(root)
    folder = _path(root, ".specify/exchange/releases/" + environment)
    history = [load(_path(root, p.relative_to(root).as_posix())) for p in sorted(folder.glob("*.json"))] if folder.exists() else []
    authority = _config(root).get("release_authority", {}).get(environment)
    result = {"ok": True, "environment": environment, "current_confirmed": False, "history_count": len(history), "errors": discovery}
    try:
        tip = _release_chain(history, _config(root)["project_id"], environment)
        _require(isinstance(authority, dict), "current authority not configured")
        repo = projects[authority["project_id"]]
        commit = _commit(repo, authority["ref"])
        fact = _json_bytes(_blob(repo, commit, authority["path"])); _real(fact)
        _require(fact.get("environment") == environment and fact.get("project_id") == _config(root)["project_id"], "authority identity mismatch")
        _require(fact.get("record_id") == tip, "authority event does not match the linear history tip")
        matches = [r for r in history if all(r.get(k) == fact.get(k) for k in RELEASE_FIELDS)]
        _require(len(matches) == 1, "authority current event has not been imported or is ambiguous")
        ref = matches[0]["source_ref"]
        pinned = validate_reference(root, ref, projects)
        _require(_json_bytes(pinned["content"]) == fact, "authority current fact changed")
        result.update(current_confirmed=True, current=fact, authority_commit=commit)
    except (ValueError, KeyError, OSError) as exc:
        result["errors"].append({"reason": str(exc)})
    return result


def register(subparsers):
    actions = subparsers.add_parser("exchange").add_subparsers(dest="exchange_action", required=True)
    for name in ("publish", "receipt"):
        p = actions.add_parser(name); p.add_argument("--input", required=True); p.add_argument("--body")
        p.set_defaults(handler=lambda a, n=name: publish(a.root, a.input, a.body, "handoff" if n == "publish" else "receipt"))
    p = actions.add_parser("scan"); p.add_argument("--context")
    p.set_defaults(handler=lambda a: scan(a.root, load(safe(a.root, a.context)) if a.context else None))
    p = actions.add_parser("check"); g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--record"); g.add_argument("--change")
    p.set_defaults(handler=lambda a: check_record(a.root, a.record) if a.record else closure(a.root, a.change))
    actions = subparsers.add_parser("release").add_subparsers(dest="release_action", required=True)
    p = actions.add_parser("record"); p.add_argument("--input", required=True)
    p.set_defaults(handler=lambda a: record_release(a.root, load(safe(a.root, a.input))))
    p = actions.add_parser("status"); p.add_argument("--environment", required=True)
    p.set_defaults(handler=lambda a: release_status(a.root, a.environment))
