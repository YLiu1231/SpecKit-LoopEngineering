"""Problem-scoped remediation and feature-wide resource accounting."""
from pathlib import Path
import math
from .common import load, save, safe, now, identifier, digest


def limits(root):
    root = Path(root).resolve()
    policy = load(safe(root, ".specify/loop-engineering/policy.json"), {})
    project = load(safe(root, ".specify/project.yaml"), {})
    remediation = policy.get("remediation", {})
    cap = project.get("resource_budget", {}).get("max_seconds", policy.get("resource_budget", {}).get("default_max_seconds"))
    if cap is not None and (isinstance(cap, bool) or not isinstance(cap, (int, float)) or not math.isfinite(cap) or cap <= 0):
        raise ValueError("resource_budget.max_seconds must be positive")
    result = {"max_attempts": remediation.get("max_attempts", 3), "max_no_progress": remediation.get("max_no_progress", 2), "max_seconds": cap}
    for k in ("max_attempts", "max_no_progress"):
        if type(result[k]) is not int or result[k] <= 0:
            raise ValueError(k + " must be a positive integer")
    return result


def state(root, feature):
    return load(safe(root, Path(feature) / "budget.json"), {"schema_version": "1.0", "attempts": [], "usage": [], "extensions": []})


def report(root, feature):
    data, policy = state(root, feature), limits(root)
    spent = sum(x["elapsed_seconds"] for x in data["attempts"] + data["usage"])
    cap = policy["max_seconds"]
    if cap is not None:
        cap += sum(x.get("extra_seconds", 0) for x in data["extensions"])
    problems = {}
    for entry in data["attempts"]:
        p = problems.setdefault(entry["problem_id"], {"attempts": 0, "no_progress": 0, "limit": policy["max_attempts"]})
        p["attempts"] += 1
        p["no_progress"] = 0 if entry["progress"] else p["no_progress"] + 1
        p["resolved"] = entry.get("resolved", False)
    for problem_id, p in problems.items():
        ext = [e for e in data["extensions"] if e.get("problem_id") == problem_id]
        p["limit"] += sum(e.get("extra_attempts", 0) for e in ext)
        # An explicit continuation creates a new stagnation window, not erased history.
        if ext:
            after = ext[-1]["attempts_at_grant"]
            p["no_progress"] = 0
            for a in [a for a in data["attempts"] if a["problem_id"] == problem_id][after:]:
                p["no_progress"] = 0 if a["progress"] else p["no_progress"] + 1
        p["action"] = "resolved" if p.get("resolved") else "escalate" if p["attempts"] >= p["limit"] or p["no_progress"] >= policy["max_no_progress"] else "continue"
    return {"ok": True, "elapsed_seconds": spent, "max_seconds": cap,
            "resource_action": "configure_budget" if cap is None else ("escalate" if spent >= cap else "continue"),
            "problems": problems, "policy": policy}


def consume(root, feature, seconds, kind, reference):
    if not isinstance(seconds, (float, int)) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError("Invalid resource duration")
    data = state(root, feature)
    data["usage"].append({"kind": kind, "reference": reference, "elapsed_seconds": seconds, "at": now()})
    save(safe(root, Path(feature) / "budget.json"), data)
    return report(root, feature)


def record(root, feature, entry):
    required = ("problem_id", "attempt_id", "loop", "hypothesis", "evidence_refs", "progress", "elapsed_seconds")
    if not isinstance(entry, dict) or any(k not in entry for k in required):
        raise ValueError("Attempt requires " + ", ".join(required))
    if entry.get("example") or str(entry.get("evidence_kind", "")).startswith("synthetic"):
        raise ValueError("Example attempts cannot be recorded as remediation evidence")
    identifier(entry["problem_id"]); identifier(entry["attempt_id"])
    if entry["loop"] not in ("requirements", "design", "implementation", "convergence"):
        raise ValueError("Unknown loop")
    if type(entry["progress"]) is not bool or not entry["hypothesis"]:
        raise ValueError("Explicit hypothesis and boolean progress are required")
    seconds = entry["elapsed_seconds"]
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError("Invalid attempt duration")
    if not isinstance(entry["evidence_refs"], list) or not entry["evidence_refs"]:
        raise ValueError("A reassessment needs evidence")
    for ref in entry["evidence_refs"]:
        if not isinstance(ref, dict) or not ref.get("path") or not ref.get("digest"):
            raise ValueError("Evidence refs require path and digest")
        from .common import file_digest
        if file_digest(safe(root, ref["path"])) != ref["digest"]:
            raise ValueError("Attempt evidence has changed")
    if entry["progress"] and not entry.get("progress_reason"):
        raise ValueError("Progress requires a concrete evidence-based reason")
    if entry.get("resolved") and not entry["progress"]:
        raise ValueError("Resolution requires evidenced progress")
    data = state(root, feature)
    prior = next((a for a in data["attempts"] if a["attempt_id"] == entry["attempt_id"]), None)
    if prior:
        if prior["input_digest"] != digest(entry):
            raise ValueError("Attempt ID reused with different content")
        return report(root, feature)
    current = report(root, feature)
    if current["resource_action"] != "continue" or current["problems"].get(entry["problem_id"], {}).get("action") == "escalate":
        raise ValueError("Budget requires an explicit continuation before another attempt")
    data["attempts"].append(dict(entry, input_digest=digest(entry), at=now()))
    save(safe(root, Path(feature) / "budget.json"), data)
    return report(root, feature)


def resume(root, feature, grant):
    for k in ("id", "actor", "source", "reason"):
        if not grant.get(k):
            raise ValueError("Continuation requires " + k)
    identifier(grant["id"])
    if grant.get("accepted") is not True or grant.get("example"):
        raise ValueError("Continuation must record an actual accepted decision")
    extra_attempts, extra_seconds = grant.get("extra_attempts", 0), grant.get("extra_seconds", 0)
    if type(extra_attempts) is not int or extra_attempts < 0:
        raise ValueError("extra_attempts must be a nonnegative integer")
    if isinstance(extra_seconds, bool) or not isinstance(extra_seconds, (int, float)) or not math.isfinite(extra_seconds) or extra_seconds < 0:
        raise ValueError("extra_seconds must be nonnegative")
    if not extra_attempts and not extra_seconds:
        raise ValueError("A continuation must grant a finite additional budget")
    if extra_attempts:
        identifier(grant.get("problem_id"))
    data = state(root, feature)
    prior = next((g for g in data["extensions"] if g["id"] == grant["id"]), None)
    if prior:
        if prior["input_digest"] != digest(grant):
            raise ValueError("Continuation ID cannot be rewritten")
        return report(root, feature)
    data["extensions"].append(dict(grant, input_digest=digest(grant), at=now(),
        attempts_at_grant=sum(a["problem_id"] == grant.get("problem_id") for a in data["attempts"])))
    save(safe(root, Path(feature) / "budget.json"), data)
    return report(root, feature)


def register(subparsers):
    group = subparsers.add_parser("budget")
    actions = group.add_subparsers(dest="budget_action", required=True)
    for name in ("status", "record", "resume"):
        p = actions.add_parser(name)
        p.add_argument("--feature-dir", required=True)
        if name != "status":
            p.add_argument("--input", required=True)
        def handler(args, action=name):
            root = Path(args.root).resolve(); feature = safe(root, args.feature_dir)
            if action == "status":
                return report(root, feature)
            value = load(safe(root, args.input))
            return record(root, feature, value) if action == "record" else resume(root, feature, value)
        p.set_defaults(handler=handler)
