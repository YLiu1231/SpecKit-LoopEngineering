{
  "schema_version": "1.0",
  "policy_version": "2.0.0",
  "principles": {
    "intent_source": "spec-plan-tasks",
    "completion_requires_evidence": true,
    "generator_cannot_self-certify": true,
    "policy_self_modification": false,
    "external_network": "deny",
    "default_execution_scope": "project-only"
  },
  "loops": {
    "requirements": {
      "blocking_severities": [
        "critical",
        "high"
      ],
      "human_gate": "material product intent"
    },
    "design": {
      "blocking_severities": [
        "critical",
        "high"
      ],
      "human_gate": "architecture, dependency, data migration"
    },
    "implementation": {
      "batch_size": "one independently testable task or story slice",
      "human_gate": "scope change or irreversible side effect"
    },
    "convergence": {
      "max_new_tasks_per_iteration": 12,
      "human_gate": "accept residual risk or release"
    }
  },
  "global_stop_conditions": [
    "phase gate passed with fresh evidence and scoped decisions",
    "same problem exhausted attempts or stagnated",
    "feature resource budget exhausted",
    "new evidence invalidates approved intent or architecture",
    "operation exceeds authorized capability boundary"
  ],
  "evolution": {
    "automatic_policy_changes": false,
    "proposal_directory": ".specify/loop-engineering/proposals",
    "promotion_rule": "failure -> reproducible eval -> proposed rule -> human review -> versioned policy update",
    "minimum_evidence": [
      "reproduction or failing evaluation",
      "root cause",
      "candidate prevention rule",
      "false-positive analysis",
      "rollback plan"
    ]
  },
  "remediation": {
    "scope": "stable_problem_id_across_loops",
    "max_attempts": 3,
    "max_no_progress": 2,
    "normal_development_and_initial_tdd_red_count": false
  },
  "resource_budget": {
    "default_max_seconds": null,
    "configuration": "developer-confirmed project baseline and feature scope",
    "includes": "recorded remediation time and complete selftest execution"
  }
}
