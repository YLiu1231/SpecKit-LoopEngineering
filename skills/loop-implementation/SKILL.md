---
name: "loop-implementation"
description: "Run a bounded evidence-driven implementation loop over one small task or story slice using red-green-refactor, tests, and diff review."
argument-hint: "Optional task ID or story slice; otherwise choose the smallest unblocked slice"
compatibility: "Requires an active feature with a passing design loop"
user-invocable: true
disable-model-invocation: false
---

# 实施与完整自测 Loop

按 US 执行局部循环，再对每个增量执行整个项目的完整功能案例。读取 `.specify/docs/INCREMENTAL-WORKFLOW.md`，以有效 design 确认、任务、案例目录和资源预算为前提。

1. 选最小未阻塞 US/任务，明确需求引用、案例、断言、环境和完成证据。正常开发与计划内 TDD 初始红灯不计为失败整改。
2. 对缺陷先复现；对新增行为建立有真实断言的案例。实施→定向测试→诊断修复→再测，保留真实输出。静态检查和单元检查按项目约定执行，不能据其成功宣称全功能已通过。
3. 分类实现、案例、设计、需求或环境问题，只修复所属层。需求/设计问题返回相应 Loop；环境不足先解决环境，不反复修改正确业务代码。不能通过删案例或降低预期让失败消失。
4. 每个增量都运行完整登记案例（存量、新增、兼容与约定恢复案例），而非仅受影响套件：
   ```sh
   .specify/scripts/run-python.sh .specify/scripts/loopctl.py --root "$PWD" selftests run --feature-dir "$FEATURE_DIR"
   .specify/scripts/run-python.sh .specify/scripts/loopctl.py --root "$PWD" selftests check --feature-dir "$FEATURE_DIR"
   ```
   使用已配置的真实 runner 和案例级结果；必须实际执行，不能手工制造运行记录。案例目录是待执行声明，不能同时充当执行证明。退出码零而无预期案例结果、skip、超时或中断均不能算完整通过。
5. 最终行为输入包括未提交代码、运行配置、依赖、测试内容、数据前提、环境和案例目录。证据必须绑定实际输入与原始输出；其后的行为修改需要重新全量运行。纯说明文档变化可在检查不影响行为后复用。
6. 将问题、尝试、假设、证据和进展写入稳定问题记录，并用 `budget record --feature-dir "$FEATURE_DIR" --input <尝试记录.json>` 累计。达到默认 3 次自动整改、连续 2 次无实质进展或项目总预算时保存检查点并升级。跨 Loop 不清零；补充授权使用 `budget resume` 增加额度并保留历史。
7. 完整执行但仍有失败时，保留失败结果，按严重程度与真实开发决定处理风险。未完整执行规定案例时保持不完整，不能用条件准出绕过。
8. 完成任务与证据关联后运行：
   ```sh
   .specify/scripts/run-python.sh .specify/scripts/loopctl.py --root "$PWD" gate evaluate implementation --feature-dir "$FEATURE_DIR" --record
   ```
   准出决定、执行完整性、证据结论和风险处置分别报告；`conditional_pass` 不表示自测通过，`hold` 不能自动进入收敛。

现有沙箱和授权边界继续适用。普通授权范围内的本仓编辑与测试可自主执行；不规避 deny，不擅自安装新依赖、访问现网、跨仓修改、提交或发布。
