# Skill 与运行时代码的关系

团队仍通过 `/loop-init` 和四个 `/loop-*` 开始工作。Skill 是给 Agent 的工作规则；Agent 理解项目、生成需求和设计、编写业务代码，并调用本地运行器。运行器负责重复执行、记录事实和核对准出，不独立替代业务判断。

```text
用户的描述 / PRD
  → Loop Skill 指导 Agent 分析、澄清、设计和实现
  → Agent 调用 loopctl 执行器
  → 项目中的规格、上下文、案例结果、问题与交接记录
  → Agent 根据检查结果继续、回流或提交开发决策
```

| 入口 | Agent 按 Skill 完成 | 运行时提供的动作 |
| --- | --- | --- |
| loop-init | 项目整体理解、架构和边界梳理、既有问题分级 | project init/inspect/baseline；knowledge refresh/check |
| loop-requirements | 结合当前事实、相关历史与外部变化形成 FR/US；澄清实质决定 | context build/check；exchange scan；gate prepare/evaluate |
| loop-design | 概要设计、US 设计、全功能案例、版本兼容与恢复方案 | 追溯校验、四组合结构校验、设计确认绑定 |
| loop-implementation | 按 US 编码、诊断、修复，归属问题回到相应环节 | selftests run/check/export；budget record/resume；implementation gate |
| loop-convergence | 一致性评审、问题分流、刷新项目现状、记录核心改动与理念 | 最终输入与原始结果复核；知识新鲜度；交接版本核对；convergence gate |

`speckit-specify/plan/tasks/implement/converge` 等原技能继续承担具体生成和开发工作；Loop Skill 为它们组织循环节点和准出。新增 Python 代码属于框架，不是替业务项目生成的功能代码，也不要求另建服务器、数据库或常驻监听器。

## 安装位置

- 源码的 `skills/*/SKILL.md` 安装到选定 `CLAUDE_HOME/skills/`，默认 `~/.claude/skills/`。
- 本地执行器安装到业务项目 `.specify/scripts/loopctl.py` 与 `.specify/scripts/loop_runtime/`。
- 项目配置、当前知识、边界、案例目录和交接放在各自仓库 `.specify/`；单特性产物放在 `specs/<feature>/`。
- 本机路径映射和原始执行输出位于 `.specify/local/`，不作为跨项目自动共享内容；审核后的共享证据由 selftests export 输出，再通过现有 Git 流程同步。

## 判断与校验的边界

Skill 指导 Agent 分析“需求是否正确、哪些交互相关、架构如何保持稳定”；开发者确认取舍。代码检查“引用是否匹配、规定案例是否实际完整运行、原始报告是否支持摘要、目标组合是否改变、预算是否耗尽”。两层共同工作，不能将结构检查通过解释为业务正确性已获独立证明。

执行细节、字段和真实命令见 [运行手册](INCREMENTAL-WORKFLOW.md)，验证范围见 [验证记录](VALIDATION.md)。
