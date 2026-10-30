"""Validate explicit external-boundary coverage and four-version design matrices."""
from .common import load, safe, digest

CATEGORIES = ("api", "events", "shared_data", "sdk", "configuration", "business_semantics", "errors", "timing")
COMBINATIONS = ("old_old", "new_old", "old_new", "new_new")


def evaluate(root, feature, records, executed=None):
    from .gate import accepted
    errors, warnings = [], []
    review = load(safe(root, feature / "boundary-review.json"))
    if review.get("example"):
        errors.append("Boundary template is not a completed review")
    for category in CATEGORIES:
        item = review.get("categories", {}).get(category, {})
        if item.get("status") not in ("reviewed", "not_applicable") or not item.get("reason"):
            errors.append("Boundary category needs explicit review: " + category)
        if item.get("status") == "reviewed" and not item.get("source_paths"):
            errors.append("Reviewed boundary requires source evidence: " + category)
        for path in item.get("source_paths", []):
            if not safe(root, path).is_file():
                errors.append("Boundary source is unavailable: " + path)
    if review.get("unknowns"):
        if not accepted(records, "boundary_unknowns", digest(review)):
            errors.append("Unresolved boundary dependencies require an explicit scoped decision")
        warnings.append("Boundary inventory retains unresolved dependencies")
    value = load(safe(root, feature / "compatibility.json"))
    if value.get("example"):
        errors.append("Compatibility template is not a completed design")
    targets = load(safe(root, feature / "context-lock.json"), {}).get("target_dependency_set", {})
    pairs = value.get("interactions", [])
    if not pairs and not value.get("no_external_change_reason"):
        errors.append("Specify external interactions or an explicit no-change reason")
    if targets and not pairs:
        errors.append("Selected external dependencies require compatibility design")
    cat = load(safe(root, ".specify/selftests/catalog.yaml"))
    catalog = {c["id"]: c for c in cat.get("cases", [])}
    results = {c["case_id"]: c for c in executed.get("case_results", [])} if executed else {}
    for pair in pairs:
        pid = pair.get("peer_project")
        if pid not in targets:
            errors.append("Interaction requires an explicitly selected external target: " + str(pid))
        if not pair.get("contract_ids") or not pair.get("support_window"):
            errors.append("Interaction requires contract IDs and a finite stated support window")
        for side in ("local", "peer"):
            versions = pair.get(side + "_versions", {})
            if not versions.get("old") or not versions.get("new"):
                errors.append("Interaction needs explicit old/new " + side + " versions")
        rows = pair.get("combinations", {})
        if set(rows) != set(COMBINATIONS):
            errors.append("Four version combinations are mandatory for " + str(pid))
        for combination in COMBINATIONS:
            row = rows.get(combination, {})
            ids = row.get("case_ids", [])
            if not row.get("expected_behavior") or not ids or not set(ids) <= set(catalog):
                errors.append("Combination needs expected behavior and registered cases: " + combination)
            if combination == "old_new" and not row.get("new_capability_degradation"):
                errors.append("old_new requires explicit new-capability degradation behavior (or reason it is unnecessary)")
            for cid in ids:
                case = catalog.get(cid, {})
                if case.get("compatibility_combination") != combination or case.get("peer_project") != pid:
                    errors.append("Case must declare its exact compatibility combination and peer: " + cid)
                local_side, peer_side = combination.split("_")
                expected_versions = {"local": pair.get("local_versions", {}).get(local_side), "peer": pair.get("peer_versions", {}).get(peer_side)}
                if case.get("versions") != expected_versions:
                    errors.append("Case version inputs differ from matrix: " + cid)
                if executed and results.get(cid, {}).get("status") not in ("pass", "fail"):
                    errors.append("Compatibility case was not completely executed: " + cid)
        recovery = pair.get("recovery", {})
        if not recovery.get("stateful_effects") or type(recovery.get("independent_rollback_supported")) is not bool:
            errors.append("Recovery needs stateful effects and an explicit independent rollback judgment")
        if recovery.get("independent_rollback_supported") is False:
            if not recovery.get("alternative") or not recovery.get("limitations") or not accepted(records, "recovery_exception", digest(recovery)):
                errors.append("Restricted rollback needs a content-bound developer decision and alternative recovery")
        recovery_cases = recovery.get("case_ids", [])
        if not recovery_cases or not set(recovery_cases) <= set(catalog):
            if not accepted(records, "recovery_unverified", digest(recovery)):
                errors.append("Recovery without drill cases needs an explicit unverified-risk decision")
            else:
                warnings.append("Recovery accepted as unverified; approval is not drill evidence")
        elif executed and any(results.get(cid, {}).get("status") not in ("pass", "fail") for cid in recovery_cases):
            errors.append("Recovery drill execution incomplete")
    return {"ok": not errors, "errors": errors, "warnings": warnings}
