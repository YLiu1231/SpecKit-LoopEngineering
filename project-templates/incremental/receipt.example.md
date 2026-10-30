---
{
  "example": true,
  "protocol_version": "0.1-draft",
  "record_type": "receipt",
  "producer_project": "producer-example",
  "consumer_project": "consumer-example",
  "change_id": "producer-example.change-001",
  "receipt_id": "consumer-example.receipt-001",
  "revision": 1,
  "handoff_revision": 1,
  "handoff_ref": {"project_id": "producer-example", "kind": "handoff", "storage": "git", "ref": "REPLACE_WITH_FIXED_COMMIT", "path": ".specify/exchange/outbox/producer-example.change-001/r1.md", "content_digest": "sha256:REPLACE_WITH_HANDOFF_FILE_DIGEST"},
  "contract_assumptions": [{"contract_id": "example-contract", "content_digest": "sha256:REPLACE_WITH_ADOPTED_CONTRACT_DIGEST"}],
  "target_dependency_set": {},
  "status": "not_assessed",
  "recheck_required": true,
  "affected_features": [],
  "source_refs": [],
  "evidence_refs": [],
  "decision_refs": [],
  "release_assumptions": [],
  "reason": "REPLACE with the consumer's actual assessment; this example has not assessed impact",
  "observed_at": "REPLACE_WITH_ACTUAL_ISO8601_TIME"
}
---

# 消费方回执示例

这是尚未判断的格式模板，不是“无影响”或“验证通过”的证明。`example: true` 和占位引用不能导入真实记录。真实回执由消费方在自己的仓库写入，生产方不能代为确认。

## 本项目使用方式与影响

填写调用入口、数据/事件/配置用途及证据，说明哪些行为受影响、哪些事实仍缺失。contract_assumptions 的摘要必须与所引用交接的对应契约相符。

## 目标组合与确认

选择未合并设计时，target_dependency_set 使用项目 ID 为键；每项包含 release_id、`basis_kind: "confirmed_design"` 和精确 basis_ref，并附本项目消费方确认。将实际 `scope: "external_design"` 决定的固定 Git 引用加入 decision_refs，决定绑定该设计的 content_digest。

示例保持 not_assessed。实际状态可为 not_assessed、unaffected、adaptation_required、adapting、verified、deferred 或 blocked，选择必须有事实依据。

## 适配与自测

- unaffected：附本项目使用方式源码证据，以及绑定 change_id 的真实 impact 决定。
- verified：设置 feature_id 绑定本仓 `specs/<feature_id>/context-lock.json`，并附同一目标依赖组合的完整真实执行报告和可共享原始输出；局部案例通过不能冒充整项目全绿。
- deferred：明确适用版本、范围、理由及实际 deferral 决定；接受延期不表示联合兼容就绪。

## 重判条件与遗留项

记录契约、目标组合、证据或现网前提改变后需重新判断的范围。依赖环境现状时，release_assumptions 固定 project_id/environment/record_id；无法确定现网状态则保留未知。
