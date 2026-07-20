#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CLAUDE_HOME_DIR=${CLAUDE_HOME:-"$HOME/.claude"}
PYTHON_BIN=${PYTHON_BIN:-}

case "$(uname -s 2>/dev/null || printf unknown)" in
  MINGW*|MSYS*|CYGWIN*)
    printf '%s\n' \
      "ERROR: Native Windows must use PowerShell: .\\install.ps1" \
      "For strict OS sandboxing, run this install.sh inside WSL2." >&2
    exit 2
    ;;
esac

usage() {
  printf '%s\n' \
    "Portable Spec Kit + Four-Loop Engineering" \
    "" \
    "Usage:" \
    "  ./install.sh install              Install globally for the current user" \
    "  ./install.sh project [DIR]        Initialize/update one project" \
    "  ./install.sh all [DIR]            Global install, then initialize project" \
    "  ./install.sh doctor               Read-only installation check" \
    "" \
    "Environment:" \
    "  SPECIFY_CLI_SOURCE=/path/pkg      Internal wheel, directory, or package source" \
    "  ALLOW_ONLINE_INSTALL=1             Permit uv to download specify-cli" \
    "  SKIP_SPECIFY_CLI=1                Skip Spec Kit CLI installation" \
    "  FORCE_CONSTITUTION=1              Replace an established project constitution" \
    "  CLAUDE_HOME=/custom/path          Override ~/.claude" \
    "  PYTHON_BIN=/path/python3          Override Python 3 executable"
}

find_python() {
  if [ -n "$PYTHON_BIN" ]; then
    if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(sys.version_info < (3, 9))'; then
      printf '%s\n' "ERROR: PYTHON_BIN must point to Python 3.9+." >&2
      exit 2
    fi
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=$(command -v python3)
  elif command -v python >/dev/null 2>&1 && python -c 'import sys; raise SystemExit(sys.version_info < (3, 9))'; then
    PYTHON_BIN=$(command -v python)
  else
    printf '%s\n' "ERROR: Python 3.9+ is required." >&2
    exit 2
  fi
}

check_bundle() {
  for required in \
    "$SCRIPT_DIR/CLAUDE.md" \
    "$SCRIPT_DIR/PROJECT-CONSTITUTION.md" \
    "$SCRIPT_DIR/runtime/global_installer.py.md" \
    "$SCRIPT_DIR/runtime/bootstrap_project.py.md" \
    "$SCRIPT_DIR/runtime/loopctl.py.md" \
    "$SCRIPT_DIR/runtime/run-python.sh.md" \
    "$SCRIPT_DIR/runtime/security_guard.py.md" \
    "$SCRIPT_DIR/runtime/policy.json.md" \
    "$SCRIPT_DIR/runtime/workflow.yml.md"; do
    if [ ! -f "$required" ]; then
      printf '%s\n' "ERROR: Bundle is incomplete: $required" >&2
      exit 2
    fi
  done
}

install_specify_cli() {
  if [ "${SKIP_SPECIFY_CLI:-0}" = "1" ]; then
    printf '%s\n' "Spec Kit CLI installation skipped by SKIP_SPECIFY_CLI=1."
    return
  fi
  if command -v specify >/dev/null 2>&1; then
    printf '%s\n' "Spec Kit CLI already available: $(command -v specify)"
    return
  fi

  if [ -n "${SPECIFY_CLI_SOURCE:-}" ]; then
    if command -v uv >/dev/null 2>&1; then
      uv tool install "$SPECIFY_CLI_SOURCE"
    else
      "$PYTHON_BIN" -m pip install --user "$SPECIFY_CLI_SOURCE"
    fi
  elif [ "${ALLOW_ONLINE_INSTALL:-0}" = "1" ] && command -v uv >/dev/null 2>&1; then
    printf '%s\n' "Installing specify-cli from the configured package source..."
    uv tool install specify-cli
  else
    printf '%s\n' \
      "INFO: specify CLI is unavailable; no network request was made." \
      "Direct skills still work through the offline project bootstrap." \
      "For full CLI support, provide SPECIFY_CLI_SOURCE or set ALLOW_ONLINE_INSTALL=1." >&2
  fi
}

global_install() {
  install_specify_cli
  "$PYTHON_BIN" "$SCRIPT_DIR/runtime/global_installer.py.md" \
    --bundle-root "$SCRIPT_DIR" \
    --claude-home "$CLAUDE_HOME_DIR" \
    --platform-mode strict
  printf '%s\n' \
    "" \
    "Global installation complete." \
    "Restart Claude Code before using /loop-init or the Loop skills."
}

project_install() {
  project_dir=${1:-.}
  if [ ! -d "$project_dir" ]; then
    printf '%s\n' "ERROR: Project directory does not exist: $project_dir" >&2
    exit 2
  fi
  project_dir=$(CDPATH= cd -- "$project_dir" && pwd)

  bootstrap="$CLAUDE_HOME_DIR/loop-engineering/bootstrap_project.py"
  if [ ! -f "$bootstrap" ]; then
    printf '%s\n' "ERROR: Global runtime is missing. Run ./install.sh install first." >&2
    exit 2
  fi

  offline_flag=
  if [ ! -d "$project_dir/.specify" ]; then
    if [ "${SKIP_SPECIFY_CLI:-0}" = "1" ]; then
      printf '%s\n' "Using bundled offline Spec Kit project structure: $project_dir"
      offline_flag=--offline-init
    elif command -v specify >/dev/null 2>&1; then
      printf '%s\n' "Initializing Spec Kit in: $project_dir"
      (
        cd "$project_dir"
        specify init --here --integration claude --script sh
      )
    else
      printf '%s\n' "Using bundled offline Spec Kit project structure: $project_dir"
      offline_flag=--offline-init
    fi
  fi

  force_flag=
  if [ "${FORCE_CONSTITUTION:-0}" = "1" ]; then
    force_flag=--force-constitution
  fi

  "$PYTHON_BIN" "$bootstrap" \
    --project-root "$project_dir" \
    ${offline_flag:+$offline_flag} \
    ${force_flag:+$force_flag}

  "$PYTHON_BIN" -m py_compile "$project_dir/.specify/scripts/loopctl.py"
  "$PYTHON_BIN" "$project_dir/.specify/scripts/loopctl.py" --help >/dev/null
  printf '%s\n' \
    "" \
    "Project runtime ready: $project_dir" \
    "Start Claude in that directory and run /loop-requirements <feature>."
}

doctor() {
  status=0
  if command -v claude >/dev/null 2>&1; then
    printf '%s\n' "OK claude: $(claude --version 2>/dev/null || true)"
  else
    printf '%s\n' "MISSING claude executable" >&2
    status=1
  fi
  if command -v specify >/dev/null 2>&1; then
    printf '%s\n' "OK specify: $(specify --version 2>/dev/null || command -v specify)"
  else
    printf '%s\n' "OPTIONAL specify CLI missing; offline direct-skill mode remains available."
  fi
  for path in \
    "$CLAUDE_HOME_DIR/settings.json" \
    "$CLAUDE_HOME_DIR/CLAUDE.md" \
    "$CLAUDE_HOME_DIR/hooks/security_guard.py" \
    "$CLAUDE_HOME_DIR/skills/loop-init/SKILL.md" \
    "$CLAUDE_HOME_DIR/skills/loop-requirements/SKILL.md" \
    "$CLAUDE_HOME_DIR/skills/loop-design/SKILL.md" \
    "$CLAUDE_HOME_DIR/skills/loop-implementation/SKILL.md" \
    "$CLAUDE_HOME_DIR/skills/loop-convergence/SKILL.md" \
    "$CLAUDE_HOME_DIR/skills/speckit-specify/SKILL.md" \
    "$CLAUDE_HOME_DIR/loop-engineering/bootstrap_project.py" \
    "$CLAUDE_HOME_DIR/loop-engineering/run-python.sh"; do
    if [ -f "$path" ]; then
      printf '%s\n' "OK $path"
    else
      printf '%s\n' "MISSING $path" >&2
      status=1
    fi
  done
  if [ -f "$CLAUDE_HOME_DIR/settings.json" ]; then
    "$PYTHON_BIN" -c 'import json,sys; p=json.load(open(sys.argv[1], encoding="utf-8")); assert p["sandbox"]["enabled"] is True; assert p["sandbox"]["allowUnsandboxedCommands"] is False; assert p["sandbox"]["network"]["deniedDomains"] == ["*"]; print("OK strict offline sandbox")' "$CLAUDE_HOME_DIR/settings.json" || status=1
  fi
  return "$status"
}

find_python
check_bundle

command_name=${1:-install}
case "$command_name" in
  install)
    global_install
    ;;
  project)
    project_install "${2:-.}"
    ;;
  all)
    global_install
    project_install "${2:-.}"
    ;;
  doctor)
    doctor
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
