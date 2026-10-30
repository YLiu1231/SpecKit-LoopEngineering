"""Execute locally configured selftests; keep completeness separate from success."""
import os
import hashlib
from pathlib import Path
import shutil
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET
from .common import load, save, safe, digest, file_digest, now, snapshot, identifier, dependency_digest, parse
from . import budget


def catalog(root, path=".specify/selftests/catalog.yaml"):
    value = load(safe(root, path))
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("A nonempty complete selftest catalog is required")
    ids = []
    for case in cases:
        identifier(case.get("id")); identifier(case.get("us_id"))
        if not case.get("assertion"):
            raise ValueError("Every case requires its expected assertion")
        runner = value.get("runners", {}).get(case.get("runner_id"), case)
        if not isinstance(runner, dict) or not isinstance(runner.get("command"), list) or not runner["command"] or not all(isinstance(x, str) for x in runner["command"]):
            raise ValueError("Every case requires an executable runner argv")
        ids.append(case["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case IDs")
    if value.get("example"):
        raise ValueError("Example catalog cannot be executed as evidence")
    return value


def inputs(root, cat, feature=None):
    snap = snapshot(root, cat.get("behavior_paths"))
    config = load(safe(root, ".specify/project.yaml"), {})
    context = load(safe(root, Path(feature) / "context-lock.json"), {}) if feature else {}
    return {"base_commit": snap["base_commit"], "files": snap["files"], "code_digest": snap["digest"],
            "catalog_digest": digest(cat), "environment": cat.get("environment", "local"),
            "dependency_digest": dependency_digest(context.get("target_dependency_set", config.get("target_dependency_set", {}))),
            "production_baseline_digest": digest(context.get("production_baselines", [])),
            "data_precondition_digest": digest(cat.get("data_preconditions", {}))}


def _parse_results(path, fmt, planned):
    if not path.is_file():
        return {}, ["Runner did not produce a result file; exit code alone is insufficient"]
    return parse_result_bytes(path.read_bytes(), fmt, planned)


def parse_result_bytes(data, fmt, planned):
    results, errors = {}, []
    if fmt == "case-json":
        report = parse(data.decode("utf-8"))
        if not isinstance(report, dict):
            raise ValueError("Runner result must be an object")
        if report.get("example") or str(report.get("evidence_kind", "")).startswith("synthetic"):
            raise ValueError("Synthetic runner results are not evidence")
        rows = report.get("case_results", [report] if "case_id" in report else [])
        for row in rows:
            cid = row.get("case_id")
            if cid in results:
                raise ValueError("Duplicate result: " + str(cid))
            status = row.get("status")
            if status not in ("pass", "fail", "skipped", "error"):
                raise ValueError("Invalid case result status")
            if status in ("pass", "fail") and (type(row.get("assertions")) is not int or row["assertions"] < 1):
                raise ValueError("Completed cases require a positive assertion count")
            results[cid] = {"status": status, "assertions": row.get("assertions", 0)}
    elif fmt == "junit":
        tree = ET.fromstring(data)
        native = {}
        for case in tree.iter("testcase"):
            key = case.get("classname", "") + "::" + case.get("name", "")
            if key in native:
                raise ValueError("Duplicate JUnit testcase identity: " + key)
            status = "error" if case.find("error") is not None else "fail" if case.find("failure") is not None else "skipped" if case.find("skipped") is not None else "pass"
            native[key] = {"status": status, "native_id": key}
        for case in planned:
            if case.get("native_id") in native:
                results[case["id"]] = native.pop(case["native_id"])
        if native:
            errors.append("JUnit contains unregistered cases; refresh the complete catalog: " + ", ".join(sorted(native)))
    else:
        raise ValueError("result_format must be case-json or junit")
    extra = set(results) - {c["id"] for c in planned}
    if extra:
        errors.append("Unregistered case results: " + ", ".join(sorted(extra)))
    return results, errors



def validate_collected(record, planned_cases, read_bytes):
    """Recompute conclusions from original runner bytes, locally or from Git."""
    errors = []
    cat = record.get("catalog_snapshot")
    if not isinstance(cat, dict) or digest(cat) != record.get("input_snapshot", {}).get("catalog_digest"):
        return ["Collected evidence lacks a valid catalog snapshot"]
    if cat.get("cases") != planned_cases:
        errors.append("Collected catalog cases differ from the required full catalog")
    planned = [c["id"] for c in planned_cases]
    rows = record.get("case_results", [])
    actual = {r.get("case_id"): r for r in rows}
    if record.get("planned_case_ids") != planned or len(actual) != len(rows) or set(actual) != set(planned):
        errors.append("Collected case summary does not cover the full catalog exactly")
    groups = {}
    for case in planned_cases:
        rid = case.get("runner_id", "case-" + case["id"])
        groups.setdefault(rid, []).append(case)
    commands = record.get("commands", [])
    command_ids = [c.get("runner_id") for c in commands]
    if len(set(command_ids)) != len(command_ids) or set(command_ids) != set(groups):
        errors.append("Collected commands do not cover every runner exactly once")
    collected = {}
    for command in commands:
        try:
            rid = command["runner_id"]
            selected = groups.get(rid, [])
            expected_ids = [c["id"] for c in selected]
            if not selected or command.get("planned_case_ids") != expected_ids:
                errors.append("Runner case scope mismatch: " + str(rid))
                continue
            conf = cat.get("runners", {}).get(rid, selected[0])
            if command.get("result_format") != conf.get("result_format", "case-json"):
                errors.append("Runner result format changed: " + rid)
            contents = {}
            for key in ("output", "result"):
                raw = read_bytes(command[key + "_ref"])
                if "sha256:" + hashlib.sha256(raw).hexdigest() != command.get(key + "_digest"):
                    errors.append("Collected " + key + " hash mismatch: " + rid)
                contents[key] = raw
            parsed, parser_errors = parse_result_bytes(contents["result"], command["result_format"], selected)
            errors.extend(parser_errors)
            if set(parsed) != set(expected_ids):
                errors.append("Original runner results omit or add planned cases: " + rid)
            if type(command.get("exit_code")) is not int or (command["exit_code"] != 0 and parsed and all(r["status"] == "pass" for r in parsed.values())):
                errors.append("Runner exit code contradicts collected results: " + rid)
            for cid, row in parsed.items():
                if cid in collected:
                    errors.append("Case executed by multiple runner records: " + str(cid))
                collected[cid] = row
                if any(actual.get(cid, {}).get(k) != v for k, v in row.items()):
                    errors.append("Case summary contradicts original runner result: " + str(cid))
            for case in selected:
                if actual.get(case["id"], {}).get("us_id") != case["us_id"]:
                    errors.append("Case story identity mismatch: " + case["id"])
        except (ValueError, KeyError, TypeError, AttributeError, OSError, UnicodeError, ET.ParseError) as exc:
            errors.append("Cannot verify original runner evidence: " + str(exc))
    if set(collected) != set(planned):
        errors.append("Original execution evidence does not cover the full catalog")
    if any(row.get("status") not in ("pass", "fail") for row in collected.values()):
        errors.append("Original execution contains incomplete cases")
    verdict = "fail" if any(row.get("status") == "fail" for row in collected.values()) else "pass" if not errors else "inconclusive"
    if record.get("execution_state") != "complete" or record.get("errors") or record.get("interrupted"):
        errors.append("Recorded execution is incomplete")
    if record.get("evidence_verdict") != verdict:
        errors.append("Recorded verdict contradicts original execution")
    return errors

def run_suite(root, feature, catalog_path=".specify/selftests/catalog.yaml"):
    root = Path(root).resolve(); feature = safe(root, feature)
    if not feature.is_dir():
        raise ValueError("Feature directory does not exist")
    cat = catalog(root, catalog_path)
    limit = budget.report(root, feature)
    if limit["resource_action"] != "continue":
        raise ValueError("Configure or extend feature resource budget before execution")
    initial = inputs(root, cat, feature)
    run_id = "run-" + uuid.uuid4().hex
    local = safe(root, ".specify/local/selftests/" + run_id)
    local.mkdir(parents=True)
    jobs = {}
    for case in cat["cases"]:
        rid = case.get("runner_id", "case-" + case["id"])
        identifier(rid)
        conf = cat.get("runners", {}).get(rid, case if "command" in case else None)
        if not isinstance(conf, dict) or not isinstance(conf.get("command"), list) or not conf["command"] or not all(isinstance(x, str) for x in conf["command"]):
            raise ValueError("Runner needs command argv: " + rid)
        safe(root, conf.get("cwd", "."))
        timeout = conf.get("timeout_seconds", 300)
        if type(timeout) not in (int, float) or not 0 < timeout <= 86400:
            raise ValueError("Invalid runner timeout")
        jobs.setdefault(rid, {"config": conf, "cases": []})["cases"].append(case)
    started = time.monotonic(); all_results = {}; records = []; errors = []
    interrupted = False
    try:
        for rid, job in jobs.items():
            remaining = limit["max_seconds"] - limit["elapsed_seconds"] - (time.monotonic() - started)
            if remaining <= 0:
                errors.append("Resource budget exhausted before all cases executed"); break
            conf = job["config"]
            output = local / (rid + ".log"); result_path = local / (rid + ".result")
            command = [x.replace("{result_file}", str(result_path)) for x in conf["command"]]
            env = dict(os.environ, LOOP_RESULT_FILE=str(result_path), LOOP_RUN_ID=run_id)
            code = None; runner_error = None
            try:
                with output.open("wb") as out:
                    proc = subprocess.run(command, cwd=safe(root, conf.get("cwd", ".")), env=env,
                        stdout=out, stderr=subprocess.STDOUT, timeout=min(conf.get("timeout_seconds", 300), remaining), check=False)
                    code = proc.returncode
                safe(root, result_path); safe(root, output)
                parsed, parsing_errors = _parse_results(result_path, conf.get("result_format", "case-json"), job["cases"])
                errors.extend(parsing_errors)
                if code != 0 and parsed and all(x["status"] == "pass" for x in parsed.values()):
                    runner_error = "Nonzero exit contradicts passing results"
                if not runner_error:
                    all_results.update(parsed)
            except (OSError, subprocess.TimeoutExpired, ValueError, ET.ParseError) as exc:
                runner_error = type(exc).__name__ + ": " + str(exc)
            if runner_error:
                errors.append(rid + ": " + runner_error)
                for case in job["cases"]:
                    all_results[case["id"]] = {"status": "error", "reason": runner_error}
            available = {}
            for label, p in (("output", output), ("result", result_path)):
                try:
                    available[label] = safe(root, p).is_file()
                except ValueError:
                    available[label] = False
            records.append({"runner_id": rid, "command": command, "exit_code": code,
                            "result_format": conf.get("result_format", "case-json"),
                            "planned_case_ids": [c["id"] for c in job["cases"]],
                            "output_ref": output.relative_to(root).as_posix() if available["output"] else None,
                            "output_digest": file_digest(output) if available["output"] else None,
                            "result_ref": result_path.relative_to(root).as_posix() if available["result"] else None,
                            "result_digest": file_digest(result_path) if available["result"] else None})
    except KeyboardInterrupt:
        interrupted = True; errors.append("Execution interrupted; remaining cases were not executed")
    finally:
        elapsed = time.monotonic() - started
        budget.consume(root, feature, elapsed, "selftests", run_id)
    try:
        final = inputs(root, catalog(root, catalog_path), feature)
    except (ValueError, OSError) as exc:
        final = initial
        errors.append("Behavior inputs unavailable after execution: " + str(exc))
    if initial != final:
        # HEAD alone may move while identical working inputs remain; use the actual content below.
        if any(initial[k] != final[k] for k in initial if k != "base_commit"):
            errors.append("Behavior inputs changed during execution")
    rows = [dict(all_results.get(c["id"], {"status": "not_run"}), case_id=c["id"], us_id=c["us_id"]) for c in cat["cases"]]
    complete = not errors and all(r["status"] in ("pass", "fail") for r in rows)
    verdict = "fail" if any(r["status"] == "fail" for r in rows) else "pass" if complete else "inconclusive"
    result = {"schema_version": "1.0", "record_type": "selftest_run", "run_id": run_id,
              "project_id": load(safe(root, ".specify/project.yaml"), {}).get("project_id"), "feature_id": feature.name,
              "created_at": now(), "catalog_path": str(Path(catalog_path)), "catalog_snapshot": cat, "input_snapshot": initial,
              "planned_case_ids": [c["id"] for c in cat["cases"]], "case_results": rows, "commands": records,
              "execution_state": "complete" if complete else "incomplete", "evidence_verdict": verdict,
              "elapsed_seconds": elapsed, "errors": errors, "interrupted": interrupted}
    target = safe(root, feature / "evidence/runs" / (run_id + ".json")); save(target, result)
    save(safe(root, feature / "evidence/latest.json"), {"path": target.relative_to(root).as_posix(), "digest": file_digest(target)})
    return dict(result, ok=complete and verdict == "pass", record_path=target.relative_to(root).as_posix())


def check(root, feature, catalog_path=".specify/selftests/catalog.yaml"):
    root = Path(root).resolve(); feature = safe(root, feature)
    errors = []; cat = catalog(root, catalog_path)
    pointer = load(safe(root, feature / "evidence/latest.json"))
    path = safe(root, pointer["path"])
    if file_digest(path) != pointer.get("digest"):
        errors.append("Selftest record changed after collection")
    record = load(path)
    if record.get("example") or str(record.get("evidence_kind", "")).startswith("synthetic"):
        errors.append("Synthetic evidence is forbidden")
    expected = inputs(root, cat, feature); prior = record.get("input_snapshot", {})
    if record.get("project_id") != load(safe(root, ".specify/project.yaml"))["project_id"] or record.get("feature_id") != feature.name:
        errors.append("Evidence belongs to a different project or feature")
    errors.extend(record.get("errors", []))
    if any(expected[k] != prior.get(k) for k in expected if k != "base_commit"):
        errors.append("Final candidate no longer matches tested behavior inputs")
    planned = [c["id"] for c in cat["cases"]]
    rows = record.get("case_results", [])
    if record.get("planned_case_ids") != planned or sorted(r.get("case_id", "") for r in rows) != sorted(planned):
        errors.append("Full catalog coverage mismatch")
    if not record.get("commands"):
        errors.append("No collected execution evidence")
    errors.extend(validate_collected(record, cat["cases"], lambda path: safe(root, path).read_bytes()))
    complete = not errors and record.get("execution_state") == "complete" and all(r.get("status") in ("pass", "fail") for r in rows)
    verdict = "fail" if any(r.get("status") == "fail" for r in rows) else "pass" if complete else "inconclusive"
    if record.get("evidence_verdict") != verdict:
        errors.append("Recorded verdict contradicts evidence or coverage")
        complete = False
    return {"ok": complete and verdict == "pass", "execution_state": "complete" if complete else "incomplete",
            "evidence_verdict": verdict, "errors": errors, "record": record, "record_path": path.relative_to(root).as_posix()}


def export(root, feature, catalog_path=".specify/selftests/catalog.yaml"):
    root = Path(root).resolve(); feature = safe(root, feature)
    checked = check(root, feature, catalog_path)
    if checked["execution_state"] != "complete" or checked["errors"]:
        raise ValueError("Only fresh complete execution evidence can be exported")
    record = checked["record"]
    destination = safe(root, feature / "evidence/exported" / identifier(record["run_id"]))
    for cmd in record["commands"]:
        for key in ("output", "result"):
            source = safe(root, cmd[key + "_ref"])
            target = safe(root, destination / source.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and file_digest(target) != cmd[key + "_digest"]:
                raise ValueError("Exported evidence is immutable")
            shutil.copyfile(source, target)
            cmd[key + "_ref"] = target.relative_to(root).as_posix()
    target = safe(root, destination / "run.json")
    if target.exists() and load(target) != record:
        raise ValueError("Exported run is immutable")
    save(target, record)
    return {"ok": True, "path": target.relative_to(root).as_posix(), "content_digest": file_digest(target),
            "note": "Review output for project-sensitive data before committing; no Git or network action performed."}


def register(subparsers):
    sub = subparsers.add_parser("selftests").add_subparsers(dest="selftests_action", required=True)
    for action in ("run", "check", "export"):
        p = sub.add_parser(action); p.add_argument("--feature-dir", required=True)
        p.add_argument("--catalog", default=".specify/selftests/catalog.yaml")
        p.set_defaults(handler=lambda a, op=action: {"run": run_suite, "check": check, "export": export}[op](a.root, a.feature_dir, a.catalog))
