"""Phase gates: structure, bindings, execution facts and explicit decisions."""
import argparse
from pathlib import Path
import re
from .common import load, save, safe, digest, file_digest, read_record, now, behavior_allowed
from . import project, evidence, budget, exchange, compatibility

PHASES = ("requirements", "design", "implementation", "convergence")


def binding(root, feature, phase):
    root = Path(root).resolve(); feature = safe(root, feature)
    names = ["spec.md"]
    if phase != "requirements":
        names += ["plan.md", "tasks.md", "us-design.md", "compatibility.md", "compatibility.json", "boundary-review.json", "traceability.json"]
    artifacts = {}
    for name in names:
        path = safe(root, feature / name)
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if name == "tasks.md":
                text = re.sub(r"\[[xX]\]", "[ ]", text)
            artifacts[name] = digest(text)
    lock = load(safe(root, feature / "context-lock.json"), {})
    refs = {"sources": lock.get("sources", []), "target_dependency_set": lock.get("target_dependency_set", {}),
            "production_baselines": lock.get("production_baselines", []), "unknowns": lock.get("unknowns", []),
            "exchange_snapshot": lock.get("exchange_snapshot")}
    artifacts["adopted_context"] = digest(refs)
    if phase != "requirements":
        artifacts["case_catalog"] = file_digest(safe(root, ".specify/selftests/catalog.yaml"))
    return {"scope": phase, "artifact_digest": digest(artifacts), "artifacts": artifacts,
            "missing": [name for name in names if name not in artifacts]}


def decisions(root, feature):
    data = load(safe(root, Path(feature) / "decisions.json"), {"decisions": []})
    if not isinstance(data, dict) or not isinstance(data.get("decisions"), list):
        raise ValueError("decisions.json requires a decisions list")
    ids = [d.get("id") for d in data["decisions"]]
    if len(ids) != len(set(ids)) or any(not i for i in ids):
        raise ValueError("Decision IDs must be present and unique")
    return data["decisions"]


def accepted(records, scope, expected):
    return any(d.get("scope") == scope and d.get("accepted") is True and not d.get("example")
               and d.get("artifact_digest") == expected and d.get("actor") and d.get("source") and d.get("reason")
               and d.get("unresolved_material_questions") == [] for d in records)


def finding_digest(finding):
    return digest({k: v for k, v in finding.items() if k not in ("disposition", "status", "decision_id", "updated_at")})


def evaluate(root, feature, phase, record=False):
    root = Path(root).resolve(); feature = safe(root, feature)
    errors = []; warnings = []; checks = []; risk_ids = []; execution = None
    def require(key, condition, message):
        checks.append({"id": key, "passed": bool(condition), "detail": message})
        if not condition:
            errors.append(message)
    spec_path = safe(root, feature / "spec.md")
    spec = spec_path.read_text(encoding="utf-8") if spec_path.is_file() else ""
    reqs = set(re.findall(r"\bFR-\d+\b", spec))
    specified_stories = set(re.findall(r"\bUS-?\d+\b", spec))
    require("spec", bool(spec.strip()) and bool(reqs) and not re.search(r"\[NEEDS CLARIFICATION", spec), "Specification must contain FR identifiers and no unresolved clarification markers")
    require("specified-stories", bool(specified_stories), "Specification must identify every user story with stable US IDs")
    records = decisions(root, feature)
    for required_phase in ("requirements",) if phase == "requirements" else ("requirements", "design"):
        b = binding(root, feature, required_phase)
        require(required_phase + "-artifacts", not b["missing"], "Missing " + required_phase + " artifacts: " + ", ".join(b["missing"]))
        require(required_phase + "-confirmation", accepted(records, required_phase, b["artifact_digest"]), "Current " + required_phase + " needs its content-bound developer decision")
    for name in ("spec.md",) if phase == "requirements" else ("spec.md", "plan.md", "us-design.md", "compatibility.md"):
        path = safe(root, feature / name)
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if text.startswith("---\n"):
                frontmatter = text[4:].split("\n---\n", 1)[0]
                require("artifact-not-example-" + name, not re.search(r'"example"\s*:\s*true', frontmatter), "Example artifact cannot serve as approved design: " + name)
    ctx = project.check_context(argparse.Namespace(root=str(root), feature_dir=str(feature), allow_local_changes=phase in ("implementation", "convergence")))
    require("context", ctx["ok"], "Context check: " + "; ".join(ctx["errors"]))
    warnings += ctx.get("observations", [])
    observed = ctx.get("exchange_snapshot", {})
    if observed.get("errors"):
        acknowledged = accepted(records, "external_scan", observed["digest"])
        require("external-scan-gaps", acknowledged, "External scan gaps require an explicit content-bound disposition")
        if acknowledged:
            risk_ids.append("external-scan-gaps")
    bstate = budget.report(root, feature)
    require("problem-budget", not any(p["action"] == "escalate" for p in bstate["problems"].values()), "Exhausted or stalled problems require resolution evidence or explicit continuation")
    if phase != "requirements":
        require("resource-budget", bstate["resource_action"] == "continue", "Feature resource budget is unconfigured or exhausted")
    if phase != "requirements":
        cat = evidence.catalog(root)
        trace = load(safe(root, feature / "traceability.json"), {})
        require("trace-not-example", not trace.get("example"), "Example traceability is not an approved project mapping")
        stories = trace.get("stories", [])
        require("requirements-mapped", set(trace.get("requirements", [])) == reqs, "Traceability must cover exactly the specification FR identifiers")
        story_ids = [s.get("id") for s in stories]
        require("unique-stories", bool(stories) and len(story_ids) == len(set(story_ids)) and all(story_ids), "Stories must be nonempty and unique")
        require("stories-mapped", set(story_ids) == specified_stories, "Traceability must cover exactly every specified US, including stories sharing the same FR")
        cases = {c["id"]: c for c in cat["cases"]}
        task_text = (feature / "tasks.md").read_text(encoding="utf-8") if (feature / "tasks.md").is_file() else ""
        tasks = set(re.findall(r"\bT\d+\b", task_text))
        covered = set()
        for story in stories:
            rs, ts, cs = story.get("requirements", []), story.get("tasks", []), story.get("cases", [])
            valid = bool(rs and ts and cs) and set(rs) <= reqs and set(ts) <= tasks and set(cs) <= set(cases)
            valid = valid and all(cases[c].get("us_id") == story.get("id") for c in cs if c in cases)
            require("story-" + str(story.get("id")), valid, "US must map to requirements, actual tasks and assertion-bearing catalog cases: " + str(story.get("id")))
            covered.update(rs)
        require("all-requirements", covered == reqs, "Every FR needs a US design and selftest mapping")
        require("resource-configured", budget.limits(root)["max_seconds"] is not None, "Configure a finite feature resource budget from the project baseline")
        comp = compatibility.evaluate(root, feature, records)
        require("compatibility-design", comp["ok"], "; ".join(comp["errors"]))
        warnings += comp["warnings"]
        if comp["warnings"]:
            risk_ids.append("compatibility-limitations")
    findings = load(safe(root, feature / "findings.json"), {"findings": []}).get("findings", [])
    finding_ids = [f.get("id") for f in findings]
    require("unique-findings", all(finding_ids) and len(finding_ids) == len(set(finding_ids)), "Finding IDs must be present and unique")
    accepted_cases = set()
    for f in findings:
        require("finding-severity-" + str(f.get("id")), f.get("severity") in ("critical", "high", "medium", "low", "info"), "Finding needs a supported severity: " + str(f.get("id")))
        if f.get("disposition", f.get("status")) in ("remediated", "resolved"):
            refs = f.get("resolution_evidence", [])
            valid = bool(f.get("resolution_reason") and refs)
            for ref in refs:
                try:
                    valid = valid and file_digest(safe(root, ref["path"])) == ref["digest"]
                except (ValueError, KeyError, OSError):
                    valid = False
            require("finding-resolution-" + str(f.get("id")), valid, "Resolved finding requires current resolution evidence: " + str(f.get("id")))
            continue
        is_accepted = accepted(records, "risk", finding_digest(f))
        high = f.get("severity") in ("critical", "high")
        if high and is_accepted:
            is_accepted = accepted(records, "design_exception", binding(root, feature, "design")["artifact_digest"])
        require("finding-" + str(f.get("id")), is_accepted, "Unresolved finding requires an explicit scoped decision" + (" and reevaluated design exception" if high else "") + ": " + str(f.get("id")))
        if is_accepted:
            risk_ids.append(f["id"]); accepted_cases.update(f.get("case_ids", []))
    if phase in ("implementation", "convergence"):
        execution = evidence.check(root, feature)
        require("full-execution", execution["execution_state"] == "complete" and not execution["errors"], "Full selftest execution and fresh evidence required: " + "; ".join(execution["errors"]))
        failed = {r["case_id"] for r in execution["record"].get("case_results", []) if r["status"] == "fail"}
        require("failed-case-decisions", failed <= accepted_cases, "Failed cases lack explicit risk decisions: " + ", ".join(sorted(failed - accepted_cases)))
        task_text = (feature / "tasks.md").read_text(encoding="utf-8")
        require("tasks-complete", bool(re.search(r"\[[xX]\]", task_text)) and not re.search(r"\[ \]", task_text), "All in-scope implementation tasks need explicit completion")
        comp = compatibility.evaluate(root, feature, records, execution["record"])
        require("compatibility-execution", comp["ok"], "; ".join(comp["errors"]))
    if phase == "convergence":
        kc = project.check_knowledge(argparse.Namespace(root=str(root)))
        require("knowledge-current", kc["ok"], "Current project knowledge must be refreshed: " + "; ".join(kc["errors"]))
        history = safe(root, ".specify/knowledge/features/" + feature.name + ".md")
        if history.is_file():
            meta, body = read_record(history)
            require("feature-history", not meta.get("example") and bool(body.strip()) and meta.get("feature_id") == feature.name and meta.get("input_digest") == execution["record"]["input_snapshot"]["code_digest"], "Feature history must describe the tested candidate")
        else:
            require("feature-history", False, "Feature history is missing")
        own = load(safe(root, ".specify/project.yaml"))["project_id"]
        outgoing = [m for m, p in exchange._records(root, "handoff") if m.get("feature_id") == feature.name and m.get("producer_project") == own]
        require("handoff", bool(outgoing), "A feature handoff (or explicit no-external-change assessment) is required")
        if outgoing:
            require("handoff-identity", len({m["change_id"] for m in outgoing}) == 1, "A feature must use one stable change ID with a revision chain")
            chosen = max(outgoing, key=lambda m: m["revision"])
            projects, discovered = exchange.workspace(root)
            try:
                exchange._validate(root, chosen, projects)
                impl = chosen.get("implementation_ref") or {}
                require("handoff-implemented", chosen["development_state"] in ("implemented", "merged") and bool(impl), "Convergence handoff must describe implemented code, not only a design or withdrawal")
                require("handoff-design", chosen["design_ref"].get("content_digest") == file_digest(feature / "plan.md") and chosen["compatibility_ref"].get("content_digest") == file_digest(feature / "compatibility.md"), "Handoff design references differ from current approved design")
                for contract in chosen["contract_changes"]:
                    after = contract.get("after")
                    if after:
                        require("handoff-contract-" + contract["contract_id"], file_digest(safe(root, after["path"])) == after["content_digest"], "Handoff contract differs from current candidate: " + contract["contract_id"])
                if impl.get("storage") == "local_snapshot":
                    require("handoff-candidate", impl["input_digest"] == execution["record"]["input_snapshot"]["code_digest"], "Handoff candidate differs from tested candidate")
                elif impl:
                    import hashlib
                    tested = execution["record"]["input_snapshot"]["files"]
                    behavior_paths = execution["record"].get("catalog_snapshot", {}).get("behavior_paths")
                    scopes = [safe(root, p).relative_to(root) for p in behavior_paths] if behavior_paths else None
                    git_files = {}
                    listing = exchange._git(root, "ls-tree", "-rz", "--full-tree", impl["ref"])
                    for row in listing.split(b"\0"):
                        if not row:
                            continue
                        header, raw_path = row.split(b"\t", 1)
                        mode, kind, oid = header.decode().split()
                        rel = Path(raw_path.decode("utf-8"))
                        if not behavior_allowed(rel, scopes is not None) or (scopes is not None and not any(rel == scope or scope in rel.parents for scope in scopes)):
                            continue
                        if kind != "blob" or mode not in ("100644", "100755"):
                            raise ValueError("Shared candidate includes unsupported behavior input: " + rel.as_posix())
                        content = exchange._git(root, "cat-file", "blob", oid)
                        git_files[rel.as_posix()] = "sha256:" + hashlib.sha256(content).hexdigest()
                    require("handoff-candidate", git_files == tested, "Shared implementation commit does not contain the exact tested behavior inputs")
            except (ValueError, OSError) as exc:
                require("handoff-valid", False, str(exc))
            warnings += [str(x) for x in discovered]
    decision = "hold" if errors else "conditional_pass" if risk_ids else "pass"
    result = {"ok": not errors, "phase": phase, "gate_decision": decision,
              "workflow_state": "needs_decision" if errors else "completed_with_risks" if risk_ids else "completed",
              "execution_state": execution["execution_state"] if execution else "not_started",
              "evidence_verdict": execution["evidence_verdict"] if execution else "not_evaluated",
              "accepted_risks": risk_ids, "errors": errors, "warnings": warnings, "checks": checks,
              "limitations": ["Decision records preserve supplied authorization; this local checker does not authenticate human identity or independently prove business correctness."]}
    if record:
        state_path = safe(root, feature / "gate-state.json")
        state = load(state_path, {"schema_version": "1.0", "history": []})
        state[phase] = dict(result, at=now())
        state["history"].append(state[phase])
        save(state_path, state)
    return result


def register(subparsers):
    actions = subparsers.add_parser("gate").add_subparsers(dest="gate_action", required=True)
    for action in ("prepare", "evaluate"):
        p = actions.add_parser(action); p.add_argument("phase", choices=PHASES)
        p.add_argument("--feature-dir", required=True)
        if action == "evaluate":
            p.add_argument("--record", action="store_true")
        p.set_defaults(handler=lambda a, op=action: dict(binding(a.root, a.feature_dir, a.phase), ok=True) if op == "prepare" else evaluate(a.root, a.feature_dir, a.phase, a.record))
