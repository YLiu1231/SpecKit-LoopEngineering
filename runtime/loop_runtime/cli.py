"""CLI for the incremental runtime installed beside loopctl.py."""
import argparse
import json
import os
from pathlib import Path
import sys
from . import project, evidence, budget, gate, exchange
from .common import load, safe


def main(argv=None, default_root=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=default_root or os.getcwd())
    sub = parser.add_subparsers(dest="command", required=True)
    for module in (project, evidence, budget, gate, exchange):
        module.register(sub)
    p = sub.add_parser("check", help="Compatible entry for strict incremental gates; legacy PASS is not imported")
    p.add_argument("phase", choices=gate.PHASES); p.add_argument("--feature-dir"); p.add_argument("--record", action="store_true")
    def compatibility(args):
        feature = args.feature_dir
        if not feature:
            feature = load(safe(args.root, ".specify/feature.json")).get("feature_directory")
        if not feature:
            raise ValueError("No active feature; pass --feature-dir")
        result = gate.evaluate(args.root, feature, args.phase, args.record)
        result["evaluation"] = {"loop": args.phase, "status": {"pass": "PASS", "conditional_pass": "CONDITIONAL", "hold": "FAIL"}[result["gate_decision"]], "checks": result["checks"]}
        return result
    p.set_defaults(handler=compatibility)
    p = sub.add_parser("status"); p.add_argument("--feature-dir")
    def status(args):
        feature = args.feature_dir or load(safe(args.root, ".specify/feature.json"), {}).get("feature_directory")
        if not feature:
            raise ValueError("No active feature; pass --feature-dir")
        return {"ok": True, "gates": load(safe(args.root, Path(feature) / "gate-state.json"), {}), "budget": budget.report(args.root, feature)}
    p.set_defaults(handler=status)
    try:
        args = parser.parse_args(argv)
        args.root = str(Path(args.root).resolve())
        result = args.handler(args)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if result.get("ok", not result.get("errors")) else 1
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
