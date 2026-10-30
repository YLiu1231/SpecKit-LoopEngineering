"""Shared, dependency-free IO for the local incremental runtime."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def parse(text):
    try:
        return json.loads(text, object_pairs_hook=_pairs,
                          parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Invalid number: " + x)))
    except json.JSONDecodeError as exc:
        raise ValueError("Expected JSON syntax (also the supported YAML subset): " + str(exc)) from exc


_MISSING = object()


def load(path, default=_MISSING):
    path = Path(path)
    if not path.exists() and default is not _MISSING:
        return default
    try:
        return parse(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError("Cannot read " + str(path) + ": " + str(exc)) from exc


def safe(root, relative):
    root = Path(root).resolve()
    candidate = Path(relative)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        parts = candidate.relative_to(root).parts
    except ValueError as exc:
        raise ValueError("Path is outside project: " + str(relative)) from exc
    if ".." in parts:
        raise ValueError("Parent path traversal is not allowed")
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Symbolic link is not an authorized project path: " + str(relative))
    try:
        candidate.resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError("Path escapes project") from exc
    return candidate


def save(path, value):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Refusing symlink output")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    fd, name = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def file_digest(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dependency_digest(value):
    """Ignore resolver annotations, retain the exact selected content/version."""
    def clean(item):
        if isinstance(item, dict):
            return {k: clean(v) for k, v in item.items() if k not in ("observed_ref", "resolved_commit", "availability", "confirmation_verdict") and not (k == "storage" and v == "git")}
        if isinstance(item, list):
            return [clean(v) for v in item]
        return item
    return digest(clean(value))


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}", value):
        raise ValueError("Invalid identifier: " + repr(value))
    return value


def read_record(path):
    text = Path(path).read_text(encoding="utf-8")
    if text.startswith("---\n"):
        meta, sep, body = text[4:].partition("\n---\n")
        if not sep:
            raise ValueError("Unterminated record metadata")
        value = parse(meta)
    else:
        value, body = parse(text), ""
    if not isinstance(value, dict):
        raise ValueError("Record metadata must be an object")
    return value, body


def write_record(path, meta, body):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Refusing symlink record output")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "---\n" + json.dumps(meta, ensure_ascii=False, indent=2, allow_nan=False) + "\n---\n\n" + body.strip() + "\n"
    fd, name = tempfile.mkstemp(prefix="." + path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


SNAPSHOT_SKIPPED = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache",
               ".mypy_cache", ".ruff_cache", ".ssh", ".aws", ".kube", ".docker", ".credentials", "backups"}


def behavior_allowed(rel, explicit=False):
    if set(rel.parts) & SNAPSHOT_SKIPPED or rel.name.startswith(".env") or rel.suffix in (".pyc", ".pyo"):
        return False
    if rel.name in (".netrc", ".npmrc", "credentials", "credentials.json", "auth.json", "settings.local.json", "secrets.json", "secrets.yaml", "id_rsa", "id_ed25519") or rel.suffix.lower() in (".pem", ".key", ".p12", ".pfx"):
        return False
    if not explicit and (rel.parts[0] == "specs" or
                         (rel.parts[0] == ".specify" and (len(rel.parts) < 2 or rel.parts[1] not in ("scripts", "selftests", "project.yaml")))):
        return False
    return True


def snapshot(root, paths=None):
    """Hash actual working inputs, including untracked files; never follow links.

    Default exclusions cover generated loop outputs and dependency/cache/secret
    locations. Explicit behavior_paths are reviewed project inputs and override
    generated-directory exclusion, never credential or symlink exclusions.
    """
    root = Path(root).resolve()
    candidates = []
    if paths is not None:
        if not isinstance(paths, list) or not paths:
            raise ValueError("behavior_paths must be a nonempty reviewed list")
        for entry in paths:
            p = safe(root, entry)
            if not p.exists():
                raise ValueError("Behavior input missing: " + str(entry))
            candidates.extend(p.rglob("*") if p.is_dir() else [p])
    else:
        try:
            proc = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"], capture_output=True, timeout=15)
            if proc.returncode == 0:
                candidates = [root / x for x in proc.stdout.decode("utf-8").split("\0") if x]
            else:
                raise OSError("not a git repository")
        except (OSError, subprocess.TimeoutExpired):
            for directory, dirs, names in os.walk(root, followlinks=False):
                dirs[:] = [d for d in dirs if d not in SNAPSHOT_SKIPPED and not (Path(directory) / d).is_symlink()]
                candidates.extend(Path(directory) / n for n in names)
    files = {}
    for p in sorted(set(candidates)):
        rel = p.relative_to(root)
        if not behavior_allowed(rel, paths is not None):
            continue
        p = safe(root, rel)
        if p.is_file():
            files[rel.as_posix()] = file_digest(p)
    try:
        git = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
        base = git.stdout.strip() if git.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        base = None
    return {"files": files, "digest": digest(files), "base_commit": base}
