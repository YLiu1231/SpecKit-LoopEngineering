---
name: "loop-init"
description: "Install or update the global Loop Engineering runtime in the current Spec Kit project without replacing an established project constitution."
argument-hint: "Optional: use --force-constitution only when intentionally replacing the current constitution"
compatibility: "Requires the global ~/.claude/loop-engineering runtime; Windows native uses Git Bash"
user-invocable: true
disable-model-invocation: false
---

# 初始化存量项目的增量研发 Loop

1. 核对当前目录是目标项目。读取既有 constitution、项目说明和构建入口；保留有效约束，不从实现推断未经记录的设计意图。
2. 安装或更新运行时（未建立 Spec Kit 结构时使用离线初始化）：

   ```sh
   LOOP_HOME="${CLAUDE_HOME:-$HOME/.claude}/loop-engineering"
   "$LOOP_HOME/run-python.sh" "$LOOP_HOME/bootstrap_project.py" --project-root "$PWD" --offline-init
   .specify/scripts/run-python.sh .specify/scripts/loopctl.py --root "$PWD" project init --project-id <稳定项目标识>
   .specify/scripts/run-python.sh .specify/scripts/loopctl.py --root "$PWD" project inspect
   ```

   只有用户明确要求替换 constitution 时才传 `--force-constitution`。安装完成不等于项目盘点或自测完成。
3. 读取安装后的 `.specify/docs/INCREMENTAL-WORKFLOW.md`。检查业务功能、内部架构、全部外部行为边界、构建运行、案例覆盖、月度/补丁发布、数据与恢复、历史知识和遗留问题。将事实、已批准约束、推断、未知分别记录并链接来源。
4. 根据真实项目配置 `.specify/project.yaml` 与 `.specify/selftests/catalog.yaml`。运行时的 `.yaml` 文件使用 JSON 语法子集，不安装 YAML 依赖；模板不是可直接执行的完成证明。为已授权的现有构建和自测配置真实入口、断言和结果采集，运行完整基线并保存结果。缺少环境、案例或预算时如实记录，不补造 PASS。
5. 先由开发确认有限的初次基线资源预算，再执行 `project baseline` 保存构建和完整自测结果；以测得的完整自测成本调整项目资源预算，经开发确认后设置 `resource_budget.max_seconds`。历史失败不强制清零；开发决定必须修复或提示，但失败、跳过和未知事实保持不变。
6. 执行 `knowledge refresh` 后执行 `knowledge check`，形成可持续刷新的当前摘要、逐特性历史与边界索引。未登记外部项目形成候选；本地同步由其他工具负责，Loop 不自动 fetch/pull。
7. 报告安装/保留/备份结果、基线执行证据、未执行项、有效约束、边界清单和需开发判断的问题。不得将初始化自动扩展为业务修复、发版或跨仓写入。
