---
name: "loop-convergence"
description: "Run a bounded Spec Kit convergence loop: assess present code against intent, append traceable gaps, implement them, and prove convergence without endless task growth."
argument-hint: "Optional convergence focus or residual-risk constraint"
compatibility: "Requires an active feature after at least one implementation pass"
user-invocable: true
disable-model-invocation: false
---

# 最终收敛与项目知识交接 Loop

收敛对已批准的范围、最终候选和证据作一致性判断，并把本次成果转为当前项目知识及对外交接。读取 `.specify/docs/INCREMENTAL-WORKFLOW.md`。

1. 重新执行 `exchange scan` 和 `context check --feature-dir "$FEATURE_DIR" --allow-local-changes`。检查当前规格、设计、实现、目标依赖与确认是否仍有效。相关漂移重新进入 requirements/design；无关变化不扩大范围。
2. 使用 `speckit-converge` 或独立只读评审检查已批准 FR/US、实际断言、遗漏和外部边界。新增任务必须有既有需求或已批准决策来源；不为新想法扩张任务，也不修改需求使现有实现通过。
3. 将具体问题按归属退回 requirements、design 或 implementation，保留稳定问题标识与全部整改历史。默认同问题 3 次、连续 2 次无实质进展和增量总预算共同约束；耗尽时保存检查点，不能用“收敛完成”掩盖停止。
4. 验证最终候选：
   ```sh
   .specify/scripts/run-python.sh .specify/scripts/loopctl.py --root "$PWD" selftests check --feature-dir "$FEATURE_DIR"
   ```
   若行为输入变化，重新运行 `selftests run` 的整个案例集再检查。相同候选的有效完整证据可复用；不得因换 Loop 机械重跑，也不得沿用失效证据。未完整执行时不能正常或条件准出。
5. 更新 `.specify/knowledge/current.md` 和边界索引，使其反映实际版本与候选；追加或有来源地修订本次特性历史，保留背景、批准取舍、核心改动、证据、恢复与遗留项。不能只累计日志而不刷新现状。
6. 执行 `knowledge refresh`、`knowledge check`，再执行 `context build --feature-dir "$FEATURE_DIR"` 固定更新后的本地摘要，保留原有外部版本选择。生成生产方交接并用 `exchange publish --input <本仓交接文件>` 校验发布；开发完成、合并与环境发布分别说明。收敛交接必须是 implemented/merged 并绑定完整被测输入；设计态交接和旧实现提交不能替代本次成果。自身收敛不要求所有消费者同时完成，但必须保留其未知、适配或已接受延期状态。
7. 消费方在自己仓库形成回执，使用 `exchange receipt --input <本仓回执文件>`；生产方后续扫描读取。已接受延期可形成已识别范围处置，不能证明联合兼容就绪。撤销、回滚或契约改变后重新判断相关回执；各项目各自看护，不设中央审批或跨仓写入。
8. 写明最终证据、未解决问题和处置，运行：
   ```sh
   .specify/scripts/run-python.sh .specify/scripts/loopctl.py --root "$PWD" gate evaluate convergence --feature-dir "$FEATURE_DIR" --record
   ```
   报告实际 gate、执行状态、证据结论、当前知识与交接位置。文档中的 PASS 或 CONVERGED 不授予准出，接受风险不改写失败事实。

发布流程负责提供权威版本记录，Loop 用 `release status` 读取并在节点刷新。Git commit、push、merge、部署和数据恢复必须有对应授权；本环不会自动执行。
