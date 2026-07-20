#!/usr/bin/env python3
"""Fail-closed policy hook for high-impact Claude Code tool calls.

The OS sandbox is the primary boundary where supported. This hook adds semantic
controls and human-readable decisions for operations whose impact is larger than one
normal edit/test cycle. It deliberately makes no allow decisions: safe calls continue
through Claude Code's normal permission layer and any available sandbox.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
from typing import Any


MAX_INPUT_BYTES = 1_000_000


DENY_COMMANDS: tuple[tuple[str, str], ...] = (
    ("提升为系统管理员权限", r"(?:^|[\n;&|]|\$\(|`)\s*sudo\b"),
    ("切换系统用户", r"(?:^|[\n;&|]|\$\(|`)\s*su(?:\s|$)"),
    ("递归强制删除", r"(?:^|[\n;&|]|\$\(|`)\s*rm\s+[^\n;&|]*(?:-[^\s]*r[^\s]*f|-[^\s]*f[^\s]*r)"),
    ("向远端仓库推送", r"(?:^|[\n;&|]|\$\(|`)\s*git\s+push\b"),
    ("合并远端 Pull Request", r"(?:^|[\n;&|]|\$\(|`)\s*gh\s+pr\s+merge\b"),
    ("远程登录或复制", r"(?:^|[\n;&|]|\$\(|`)\s*(?:ssh|scp|sftp)\b"),
    ("直接发起外网请求", r"(?:^|[\n;&|]|\$\(|`)\s*(?:curl|wget|nc|ncat|telnet)\b"),
    ("控制本机其他应用", r"(?:^|[\n;&|]|\$\(|`)\s*(?:open|osascript)\b"),
    (
        "绕过 Git Bash 边界调用 Windows 命令解释器",
        r"(?:^|[\n;&|]|\$\(|`)\s*(?:powershell(?:\.exe)?|pwsh(?:\.exe)?|cmd(?:\.exe)?)\b",
    ),
    (
        "调用 Windows 系统下载工具",
        r"(?:^|[\n;&|]|\$\(|`)\s*(?:bitsadmin|certutil)(?:\.exe)?\b",
    ),
    ("访问容器宿主能力", r"(?:^|[\n;&|]|\$\(|`)\s*docker\b"),
    ("操作 Kubernetes 集群", r"(?:^|[\n;&|]|\$\(|`)\s*kubectl\b"),
    ("应用或销毁基础设施", r"(?:^|[\n;&|]|\$\(|`)\s*terraform\s+(?:apply|destroy)\b"),
)

ASK_COMMANDS: tuple[tuple[str, str, str], ...] = (
    (
        "创建 Git 提交",
        r"(?:^|[\n;&|]|\$\(|`)\s*git\s+commit\b",
        "影响项目历史；可以通过新提交回退，但不应由循环自行决定。",
    ),
    (
        "改变分支或重写本地历史",
        r"(?:^|[\n;&|]|\$\(|`)\s*git\s+(?:checkout|switch|merge|rebase)\b",
        "可能覆盖未提交工作或改变基线；先确认目标分支和工作区状态。",
    ),
    (
        "新增或更新依赖",
        r"(?:^|[\n;&|]|\$\(|`)\s*(?:npm\s+(?:install|add)|pnpm\s+(?:install|add)|yarn\s+add|pip(?:3)?\s+install|uv\s+add|cargo\s+add|go\s+get)\b",
        "会改变依赖清单/锁文件和供应链面；当前策略不授权外网。",
    ),
    (
        "执行数据库结构迁移",
        r"(?:^|[\n;&|]|\$\(|`)\s*[^\n;&|]*(?:migrate|migration)(?:\s|$)",
        "可能改变持久化数据；先确认目标环境、备份和回滚方案。",
    ),
    (
        "改变文件执行权限或安装到系统路径",
        r"(?:^|[\n;&|]|\$\(|`)\s*(?:chmod\b|make\s+install\b)",
        "影响超出普通源码编辑；先确认目标路径与可回退性。",
    ),
)

SENSITIVE_NAMES = {
    ".env",
    ".netrc",
    ".npmrc",
    "id_rsa",
    "id_ed25519",
    "credentials",
}

POLICY_PATHS = (
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".claude/hooks",
    ".specify/loop-engineering/policy.json",
)


def emit(decision: str, reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision,
                    "permissionDecisionReason": reason,
                }
            },
            ensure_ascii=False,
        )
    )


def load_event() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        emit("deny", "已阻止：安全检查输入异常过大，无法可靠判断影响范围。")
        raise SystemExit(0)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        emit("deny", "已阻止：安全检查无法解析工具调用。")
        raise SystemExit(0)
    if not isinstance(value, dict):
        emit("deny", "已阻止：工具调用格式异常。")
        raise SystemExit(0)
    return value


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def check_file(tool: str, tool_input: dict[str, Any], project_root: Path) -> None:
    raw_path = tool_input.get("file_path") or tool_input.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        return

    candidate = Path(os.path.expanduser(raw_path))
    if not candidate.is_absolute():
        candidate = project_root / candidate
    resolved = candidate.resolve(strict=False)

    if not is_within(resolved, project_root):
        emit(
            "deny",
            f"已阻止：{tool} 试图访问项目目录之外的文件。项目边界为 {project_root}。",
        )
        return

    relative = resolved.relative_to(project_root).as_posix()
    if resolved.name in SENSITIVE_NAMES or resolved.name.startswith(".env."):
        emit("deny", f"已阻止：{relative} 被识别为凭据或环境密钥文件。")
        return

    if tool in {"Edit", "Write"} and any(
        relative == item or relative.startswith(item.rstrip("/") + "/")
        for item in POLICY_PATHS
    ):
        emit(
            "deny",
            f"已阻止：Loop 不能修改自己的安全策略文件 {relative}；请由人工评审后在会话外更新。",
        )


def main() -> int:
    event = load_event()
    tool = event.get("tool_name")
    tool_input = event.get("tool_input")
    if not isinstance(tool, str) or not isinstance(tool_input, dict):
        emit("deny", "已阻止：工具名称或参数缺失，无法判断安全影响。")
        return 0

    project_root = Path(
        os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    ).resolve()

    if tool.startswith("mcp__"):
        emit("deny", "已阻止：本项目采用离线基线，MCP 外部连接未列入可信清单。")
        return 0

    if tool in {"Read", "Edit", "Write"}:
        check_file(tool, tool_input, project_root)
        return 0

    if tool != "Bash":
        return 0

    command = tool_input.get("command")
    if not isinstance(command, str):
        emit("deny", "已阻止：Bash 调用缺少可检查的命令文本。")
        return 0

    for label, pattern in DENY_COMMANDS:
        if re.search(pattern, command, flags=re.IGNORECASE):
            emit(
                "deny",
                f"已阻止：该命令会{label}，超出本项目安全边界。若业务确需执行，请在受控终端中人工运行。",
            )
            return 0

    for label, pattern, impact in ASK_COMMANDS:
        if re.search(pattern, command, flags=re.IGNORECASE):
            emit("ask", f"需要你确认：{label}。{impact}")
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
