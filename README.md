# Claude Code：Spec Kit + Four-Loop 便携包

这个目录可以直接复制给同事。包内只包含 Markdown 文本、一个 POSIX 安装器
`install.sh` 和一个 Windows 安装器 `install.ps1`，不含任何 API Key、Token、模型
地址、用户名或开发者电脑的绝对路径。

安装后，Claude Code 获得：

- 10 个 Spec Kit Skill；
- 4 个有界 Engineering Loop；
- 1 个 `/loop-init` 项目初始化 Skill；
- 全局 `CLAUDE.md` 工作原则；
- 跨平台安全基线（macOS/Linux/WSL2 严格沙箱，原生 Windows 防护模式）；
- 中文高风险操作 Hook；
- 每项目的 policy、loopctl、workflow、constitution 和 Spec Kit 模板。

## 环境要求

- macOS、Linux、WSL2，或 Windows 10+；
- 已安装 Claude Code；
- Python 3.9+；
- 推荐安装 `uv`，用于安装完整的 `specify-cli`。

Linux/WSL2 还需要 Claude Code sandbox 所需的 `bubblewrap` 等系统依赖。安装器采用
fail-closed 配置：如果沙箱不可用，Claude Code 会拒绝启动，而不是无隔离运行。

原生 Windows 还需要 Git for Windows（Claude Code 的 Bash 工具依赖 Git Bash）。
Anthropic 当前不支持在原生 Windows 上运行 OS 级 Bash sandbox，因此安全等级分为：

- **推荐：Windows + WSL2**：具备与 Linux 相同的严格离线 OS 沙箱；
- **兼容：原生 Windows + Git Bash**：使用逐命令授权、deny 规则和安全 Hook，能够
  运行本套能力，但不等价于 OS 隔离。

平台依据：[Claude Code Windows 安装说明](https://code.claude.com/docs/en/setup)；
[Claude Code Bash sandbox 平台限制](https://code.claude.com/docs/en/sandboxing)。

## macOS、Linux、WSL2 一分钟安装

把整个目录复制到同事电脑，然后在系统 Terminal 中执行：

```sh
cd claude-speckit-loop-bundle
chmod +x install.sh
./install.sh install
```

安装器会：

1. 备份现有 `~/.claude/settings.json`、`CLAUDE.md`、同名 Skill 和 Hook；
2. 保留现有私有模型、代理、Token 和其他 Claude 配置；
3. 合并沙箱、权限和 Hook，不打印任何凭据值；
4. 安装 15 个全局 Skill；
5. 安装全局 Loop 运行时；
6. 将设置和备份的敏感文件权限收紧为仅本人可读。

安装后关闭并重新启动 Claude Code。

## 原生 Windows 一分钟安装

先确认已经安装 Git for Windows、Python 3.9+ 和 Claude Code，然后打开 PowerShell：

```powershell
cd C:\path\to\claude-speckit-loop-bundle
powershell -ExecutionPolicy Bypass -File .\install.ps1 all C:\path\to\project
```

如果 Git Bash 是便携安装版，先指定其路径：

```powershell
$env:CLAUDE_CODE_GIT_BASH_PATH = "C:\Program Files\Git\bin\bash.exe"
.\install.ps1 all C:\path\to\project
```

如果企业策略禁止脚本运行，请由 IT 对 `install.ps1` 做代码签名；不要修改全局
ExecutionPolicy。上面的 `Bypass` 只作用于这一次 PowerShell 进程。

## 初始化一个项目

### 方式一：完整 Spec Kit CLI

```sh
./install.sh project /path/to/project
```

原生 Windows：

```powershell
.\install.ps1 project C:\path\to\project
```

如果项目还没有 `.specify/`，脚本会调用：

```sh
specify init --here --integration claude --script sh
```

之后安装 Four-Loop policy、workflow 和确定性检查器。

### 方式二：完全离线的直接 Skill 模式

如果电脑没有 `specify` CLI，`project` 命令会从包内创建最小可运行的 `.specify`
结构，包括脚本和模板。四个 Loop 与 Spec Kit Skill 可直接运行；但
`specify workflow run/info/resume` 等 CLI 命令不可用。

```sh
SKIP_SPECIFY_CLI=1 ./install.sh all /path/to/project
```

原生 Windows：

```powershell
$env:SKIP_SPECIFY_CLI = "1"
.\install.ps1 all C:\path\to\project
```

### 内网或隔离网安装 CLI

将内部 wheel、源码目录或内部包源路径传给安装器：

```sh
SPECIFY_CLI_SOURCE=/path/to/specify_cli.whl ./install.sh install
```

原生 Windows：

```powershell
$env:SPECIFY_CLI_SOURCE = "C:\internal\specify_cli.whl"
.\install.ps1 install
```

如果安装了 `uv`，使用 `uv tool install`；否则尝试 Python user-site 安装。企业环境
建议由管理员在内部制品库提供锁定版本的 wheel，并校验哈希。

只有明确允许联网时，安装器才会从外部包源下载：

```sh
ALLOW_ONLINE_INSTALL=1 ./install.sh install
```

默认安装过程不发起网络请求。

## 开始使用

进入已初始化的项目：

```sh
cd /path/to/project
claude
```

依次执行：

```text
/loop-requirements 构建一个……
/loop-design
/loop-implementation
/loop-convergence
```

每个 Loop 都有评估器、通过条件、最大轮次、停滞检测和升级路径。人只审批：

- 产品意图与范围；
- 架构、依赖、数据迁移和安全边界；
- commit、发布、push、merge、部署等外部副作用。

在 macOS、Linux 和 WSL2 中，普通项目内读取、编辑、测试和静态检查在沙箱内自动
执行；原生 Windows 保留正常 Bash 授权提示。

## 安全模式

### macOS、Linux、WSL2：严格离线模式

默认安装的是 OS 强制执行的严格离线模式：

- Bash 子进程不能访问外网；
- WebFetch 和 MCP 默认禁用；
- 禁止 unsandboxed fallback 和 bypass permission mode；
- 禁止读取 SSH、AWS、Kube、Docker、npm 等凭据；
- API Key 和云 Token 不传给 Bash 子进程；
- 阻止 `sudo`、`rm -rf`、push、PR merge、Docker、Kubernetes、Terraform、
  `open` 和 AppleScript；
- 依赖变化、数据库迁移、Git 历史变化要求一次可理解的确认。

Claude 主进程仍可连接同事已经配置的私有模型端点；被阻断的是 Claude 启动的
Bash 子进程和外部工具。

此模式适合离线研发。若企业需要内部 Git、制品库或 MCP，不要直接开放全网；应由
管理员把策略改为内部域名窄白名单并通过 MDM 下发 managed settings。

### 原生 Windows：兼容防护模式

`install.ps1` 不会虚假启用一个不存在的沙箱。它会：

- 使用 Claude Code 的默认逐命令授权模式，不自动允许 Bash；
- 保持 WebFetch、MCP、常见下载工具、远程命令和高风险系统命令为 deny；
- 用 PreToolUse Hook 把文件操作限制在当前项目，并保护凭据和策略文件；
- 保留现有私有模型、代理和认证配置。

该模式无法阻止所有通过任意解释器构造的网络或系统调用，因此不能作为企业终端的
唯一安全边界。需要“员工只审批业务意图、普通命令自动执行”时，应使用 WSL2、开发
容器或企业管理的虚拟机，并在其中启用严格沙箱。

## 检查安装

```sh
./install.sh doctor
```

原生 Windows：

```powershell
.\install.ps1 doctor
```

它只输出程序和文件状态，不输出模型地址或凭据值。

Claude 自身检查：

```sh
claude doctor
```

进入 Claude 后还可以检查：

```text
/skills
/sandbox
```

所有平台都应看到 15 个相关 Skill。macOS、Linux、WSL2 还应看到
`Sandbox BashTool, with auto-allow` 和 strict sandbox mode；原生 Windows 应保持
普通权限模式，`install.ps1 doctor` 会检查这一点。

## 配置备份与恢复

每次安装都会生成：

```text
~/.claude/backups/portable-loop-<UTC时间>/
```

其中只保存安装器将要覆盖的原文件，目录权限为 `700`，设置备份权限为 `600`。
需要恢复时，先退出所有 Claude 会话，再由管理员或熟悉文件操作的人员从该目录恢复
对应文件。不要直接删除整个 `~/.claude`。

Windows 对应目录为 `%USERPROFILE%\.claude\backups\portable-loop-<UTC时间>\`。

## 更新

把新版目录复制到电脑，重新执行：

```sh
./install.sh install
./install.sh project /path/to/project
```

原生 Windows 对应执行：

```powershell
.\install.ps1 install
.\install.ps1 project C:\path\to\project
```

安装与项目初始化均为幂等操作；不同内容会先备份，已经一致的文件保持不变。

## 文件说明

- `CLAUDE.md`：通用工程原则和 Four-Loop 使用顺序；
- `PROJECT-CONSTITUTION.md`：新项目的默认 Agent Engineering Constitution；
- `skills/*/SKILL.md`：Spec Kit 与 Loop 技能；
- `project-templates/*.md`：Spec Kit 需求、计划、任务和清单模板；
- `runtime/*.md`：以 Markdown 文本胶囊形式携带的本地运行时；
- `spec-kit-scripts/*.md`：离线项目初始化所需的 shell 文本胶囊；
- `runtime/run-python.sh.md`：跨 macOS、Linux、WSL2、Git Bash 的 Python 启动胶囊；
- `install.sh`：macOS、Linux 和 WSL2 安装入口；
- `install.ps1`：原生 Windows PowerShell 安装入口。

文本胶囊在安装后会恢复为对应的 `.py`、`.json`、`.yml` 或 `.sh` 文件；包本身仍
只有 Markdown 与两个平台安装入口，便于审计、U 盘传输和内网分发。

**Bundle Version**: 1.1.0
**Built**: 2026-07-21

## 上游来源

Spec Kit skills、模板和辅助脚本来自 GitHub Spec Kit，并在本包中与 Four-Loop、
安全策略和离线初始化能力组合。上游项目采用 MIT License；版权与许可文本见
`SPEC-KIT-LICENSE.md`：<https://github.com/github/spec-kit>

## 许可证

本项目采用 MIT License，见 `LICENSE.md`。来自 GitHub Spec Kit 的上游内容保留其
原始版权和 MIT 许可文本，见 `SPEC-KIT-LICENSE.md`。
