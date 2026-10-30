---
name: "loop-design"
description: "Run a bounded Spec Kit design loop: plan, task decomposition, cross-artifact analysis, remediation, and architecture gate."
argument-hint: "Optional design constraints or areas that need special attention"
compatibility: "Requires an active feature with a passing requirements loop"
user-invocable: true
disable-model-invocation: false
---

# 概要设计与 US 设计 Loop

将已批准需求变为可实施的概要设计、US 设计、案例与任务。读取 `.specify/docs/INCREMENTAL-WORKFLOW.md`；以当前有效 requirements 准出和实际确认作为前提，旧文本 PASS 不足以进入本阶段。

1. 核对当前架构、模块职责、依赖方向、有效约束、边界与事实差异。重新运行 `exchange scan` 和 `context check --feature-dir "$FEATURE_DIR"`；相关外部变化使旧确认失效时先重判。
2. 使用 `speckit-plan` 输出概要设计，并编写 `us-design.md`、`compatibility.md`、`compatibility.json` 与 `boundary-review.json`。覆盖模块改动、数据流、外部契约、错误与时序、迁移及恢复。引用未合并外部设计时固定来源内容，由本项目开发明确确认；不声称该接口已实现或现网可用。
3. 定义相关新旧组合：旧旧现网基线；新生产方支持旧消费者；旧生产方与新消费者保持旧业务、明确降级新能力；新新完成新能力。兼容窗口按具体版本记录。数据、事件、配置不支持独立回退时，形成开发确认的关闭能力、补偿、联合恢复或向前修复方案及未验证项；确认不等于演练通过。
4. 每个 US 设计真实可执行的单元/功能案例、异常与边界断言及环境前提。配置 `.specify/selftests/catalog.yaml`，维持存量、新增与修改案例的完整目录。案例声明不得用 `echo PASS` 或无断言命令代替功能测试。删除案例、降低断言或改为不适用必须对应获批准的行为变更，不能在失败后排除案例。
5. 使用 `speckit-tasks` 输出按 US 分组的实施、自测、整项目全功能执行、最终复验及知识交接任务。维护 `traceability.json`，需求→US→任务→案例不能断链。替身只能用于预先约定的局部案例，不能代替明确要求真实联调的验证。
6. 用 `speckit-analyze` 只读评审结构和语义，记录问题证据。实现方案问题在本环解决；业务范围变化退回 requirements。同契约并发冲突由各项目开发各自看护；只等待受影响任务，不建立中央审批或写入其他仓库。
7. 根据 US 规模与 init 自测耗时确认增量资源预算。刷新 `knowledge refresh` 并用 `context build --feature-dir "$FEATURE_DIR"` 重建上下文（保留显式外部选择），然后执行：
   ```sh
   .specify/scripts/run-python.sh .specify/scripts/loopctl.py --root "$PWD" gate prepare design --feature-dir "$FEATURE_DIR"
   .specify/scripts/run-python.sh .specify/scripts/loopctl.py --root "$PWD" gate evaluate design --feature-dir "$FEATURE_DIR" --record
   ```
   准备对象摘要后取得真实开发确认，绑定 `decisions.json`；`hold` 不能自动进入实施。初始自测执行尚未发生时不制造结果。

设计确认后可以用 `exchange publish --input <本仓交接文件>` 主动提供目标设计交接，明确设计态和限制。实现与部署状态另行记录。整改保留稳定问题身份，执行默认同问题 3 次、连续 2 次无实质进展升级及总预算。
