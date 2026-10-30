# 安装、更新与配置

本包支持 Claude Code 的 Skill 工作流。四个 Loop 的逻辑见仓库 README，项目配置与命令见 [运行手册](INCREMENTAL-WORKFLOW.md)。

## 环境

- 已安装并可运行 Claude Code。
- Python 3.9+、Git；运行时使用 Python 标准库。
- macOS、Linux 或 WSL2 使用 `install.sh`。
- 原生 Windows 使用 PowerShell 入口 `install.ps1`；本包的项目 shell 脚本和启动器需要 Git Bash，因此还需安装 Git for Windows。

Claude Code 的平台要求见 [官方安装文档](https://code.claude.com/docs/en/setup)。Linux/WSL2 的沙箱依赖与配置见 [官方沙箱文档](https://code.claude.com/docs/en/sandboxing)。本包的原生 Windows 配置分支已有自动化检查，但 PowerShell 安装与 Windows 实际执行尚未验证。

## 一次安装到现有项目

在本包目录执行，将示例路径换成真实项目路径。

macOS、Linux 或 WSL2：

```sh
SKIP_SPECIFY_CLI=1 sh install.sh all /path/to/project
```

原生 Windows PowerShell：

```powershell
$env:SKIP_SPECIFY_CLI = "1"
.\install.ps1 all C:\path\to\project
```

如企业策略禁止未签名 PowerShell 脚本，应使用经组织批准和签名的脚本。Git Bash 为便携安装时，可先配置：

```powershell
$env:CLAUDE_CODE_GIT_BASH_PATH = "C:\Program Files\Git\bin\bash.exe"
```

安装默认不下载依赖。`SKIP_SPECIFY_CLI=1` 跳过 CLI 安装，并在目标尚未建立 `.specify/` 时使用包内离线结构。安装完成后重启 Claude Code，进入目标项目执行 `/loop-init`，建立真实基线和案例配置。

## 安装位置与保留规则

| 内容 | 默认位置 |
| --- | --- |
| 15 个 Skill | `~/.claude/skills/` |
| 全局框架运行时 | `~/.claude/loop-engineering/` |
| 工程原则、权限及 Hook 配置 | `~/.claude/CLAUDE.md`、`settings.json` 及对应 Hook 文件 |
| 项目运行器、模板、文档 | 项目内的 `.specify/` |

原生 Windows 的用户目录通常为 `%USERPROFILE%\.claude`。可用 `CLAUDE_HOME` 指定独立目录，用 `PYTHON_BIN` 指定 Python 解释器。

安装器保留既有模型、代理及其他设置，合并框架配置，不打印凭据值；已有其他 Hook 和非模板项目 constitution 保留。重复安装对一致内容保持不变，替换内容先备份。旧版 Loop 策略迁移会保留备份和自定义字段；新版自定义策略及项目业务配置继续保留。

只有确实需要替换既有 constitution 时才使用 `FORCE_CONSTITUTION=1`；这不是常规更新步骤。

## 权限与网络配置

本包在 macOS、Linux、WSL2 配置严格沙箱和禁止无沙箱重试；沙箱不可用时要求停止。默认权限限制外网访问、WebFetch、MCP、凭据读取及高风险命令，配合项目范围 Hook。Claude 主进程使用既有模型配置，shell 子进程受到沙箱限制。

原生 Windows 配置普通权限提示、deny 规则及 Hook，不启用不可用的 OS 沙箱。该模式不能阻止任意解释器构造的所有网络或系统调用，隔离能力不能等同于受支持平台的沙箱。Claude Code 的 shell 沙箱范围与限制以 [官方说明](https://code.claude.com/docs/en/sandboxing) 为准。

企业需要内部 Git、制品库或 MCP 时，应由管理员配置所需的受控访问。跨项目读取也受宿主权限约束；Loop 不会自动扩大读取范围或关闭安全策略。本地仓库同步由独立工具完成。

## 分步安装与更新

只安装当前用户的全局 Skill 和运行时：

```sh
SKIP_SPECIFY_CLI=1 sh install.sh install
```

为另一个现有项目安装或更新运行时：

```sh
SKIP_SPECIFY_CLI=1 sh install.sh project /path/to/project
```

使用新版目录重新执行 `all`，即可更新全局框架和指定项目。原生 Windows 对应使用 `.\install.ps1 install`、`.\install.ps1 project C:\path\to\project` 或 `.\install.ps1 all C:\path\to\project`；离线使用时保留 `$env:SKIP_SPECIFY_CLI = "1"`。

## 可选：完整 Spec Kit CLI

直接 Skill 模式无需 Spec Kit CLI；`specify workflow run/info/resume` 等 CLI 命令则需要对应工具和版本支持。

如需从内部制品安装 CLI，先取消跳过设置，再提供经过校验的内部 wheel、源码目录或包源：

```sh
SKIP_SPECIFY_CLI=0 SPECIFY_CLI_SOURCE=/path/to/specify_cli.whl sh install.sh install
```

```powershell
$env:SKIP_SPECIFY_CLI = "0"
$env:SPECIFY_CLI_SOURCE = "C:\internal\specify_cli.whl"
.\install.ps1 install
```

安装器优先使用 `uv tool install`，否则尝试 Python user-site 安装。离线依赖也应由内部制品库准备完整。未提供内部源时，只有明确设置 `ALLOW_ONLINE_INSTALL=1` 且存在 `uv` 才会走在线安装分支。

未强制离线、CLI 可用且项目还没有 `.specify/` 时，项目安装器会调用 `specify init --here --integration claude --script sh`；既有项目结构继续保留。已安装 CLI 的行为和网络需求由对应 CLI 版本决定。

## 检查与恢复

```sh
sh install.sh doctor
claude doctor
```

Windows 对应 `.\install.ps1 doctor`。检查不输出模型地址或凭据值；在 Claude Code 中可再用 `/skills`、`/sandbox` 核对实际状态。

全局安装备份位于：

```text
~/.claude/backups/portable-loop-<UTC时间>/
```

其中保存被替换的原文件；安装器在支持的平台收紧目录和敏感设置文件权限。需要恢复时先退出 Claude 会话，再恢复相应文件，保留不相关配置。项目运行时更新的备份位于项目 `.specify/loop-engineering/backups/`。

安装验证只证明工具和文件就绪。真实业务案例、外部边界、预算和发布来源仍由 `/loop-init` 配置与审阅。
