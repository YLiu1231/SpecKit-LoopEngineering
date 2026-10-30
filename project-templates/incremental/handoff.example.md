---
{
  "example": true,
  "protocol_version": "0.1-draft",
  "record_type": "handoff",
  "producer_project": "producer-example",
  "change_id": "producer-example.change-001",
  "feature_id": "001-example",
  "revision": 1,
  "previous_revision": null,
  "development_state": "design_confirmed",
  "baseline_release": {"status": "unknown", "reason": "REPLACE with authoritative environment evidence or retain unknown"},
  "target_release": "REPLACE_WITH_TARGET_RELEASE",
  "design_ref": {"project_id": "producer-example", "kind": "design", "storage": "git", "ref": "REPLACE_WITH_FIXED_COMMIT", "path": "specs/001-example/plan.md", "content_digest": "sha256:REPLACE_WITH_FILE_DIGEST"},
  "implementation_ref": null,
  "source_available_to_consumers": false,
  "compatibility_ref": {"project_id": "producer-example", "kind": "design", "storage": "git", "ref": "REPLACE_WITH_FIXED_COMMIT", "path": "specs/001-example/compatibility.md", "content_digest": "sha256:REPLACE_WITH_FILE_DIGEST"},
  "contract_changes": [
    {
      "contract_id": "example-contract",
      "before": null,
      "after": {"project_id": "producer-example", "kind": "contract", "storage": "git", "ref": "REPLACE_WITH_FIXED_COMMIT", "path": ".specify/knowledge/boundaries/example-contract.md", "content_digest": "sha256:REPLACE_WITH_FILE_DIGEST"},
      "change_kind": "REPLACE_WITH_ACTUAL_CHANGE_KIND",
      "compatibility_assessment": "REPLACE with preserved behavior, support window, degradation and unresolved assumptions"
    }
  ],
  "required_consumers": [{"project_id": "consumer-example", "reason": "REPLACE with potential impact", "basis": "REPLACE with source-backed usage evidence"}],
  "unknown_dependencies": ["REPLACE with actual unresolved dependencies; empty only with a justified scope"],
  "evidence_refs": [],
  "origin_chain": [],
  "created_at": "REPLACE_WITH_ACTUAL_ISO8601_TIME",
  "supersedes": [],
  "summary": "REPLACE with the actual change summary",
  "rationale": "REPLACE with the actual background and approved design rationale"
}
---

# 生产方设计交接示例

这是格式模板。`example: true`、虚构项目及占位引用不能作为真实交接导入。必须根据已确认设计和可读取的真实 Git 文件重新填写；不通过删除标记制造事实。

## 背景与批准取舍

填写业务背景、原有行为、采用方案及确认来源。生产方说明自身变化；消费方判断其使用方式是否受影响。

## 具体变化与适用版本

填写契约/语义/错误/时序变化。`design_confirmed` 表示设计已确认，不能据此宣称已实现、可联调、已合并或已部署。新契约可以 `before: null`；修改既有契约必须给出真实 before/after 引用。没有外部变化时清空 contract_changes，并填写 `no_external_change_reason`，不伪造契约变更。

## 兼容、降级与恢复

引用对应设计及其新旧组合，说明支持窗口、旧业务保持、新能力降级和恢复限制。确认方案和执行演练分别描述。

## 消费方需判断事项

列出受影响候选、依据、未知关系及建议动作。通知被读取不代表适配完成；待消费方在自己的项目内形成回执。

## 证据与限制

本示例没有执行证据。真实 implemented/merged 修订必须补充 implementation_ref；未提交本地快照保持 local_only。修改已共享交接使用新 revision，并保留前一修订，不覆盖已有回执引用。
