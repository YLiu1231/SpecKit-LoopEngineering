{
  "schema_version": "1.0",
  "policy_version": "1.0.0",
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
      "max_iterations": 3,
      "max_stagnant_iterations": 1,
      "min_score_delta": 0.05,
      "pass_score": 1.0,
      "blocking_severities": [
        "critical",
        "high"
      ],
      "human_gate": "material product intent"
    },
    "design": {
      "max_iterations": 3,
      "max_stagnant_iterations": 1,
      "min_score_delta": 0.05,
      "pass_score": 1.0,
      "blocking_severities": [
        "critical",
        "high"
      ],
      "human_gate": "architecture, dependency, data migration"
    },
    "implementation": {
      "max_iterations": 5,
      "max_stagnant_iterations": 2,
      "min_score_delta": 0.01,
      "pass_score": 1.0,
      "batch_size": "one independently testable task or story slice",
      "human_gate": "scope change or irreversible side effect"
    },
    "convergence": {
      "max_iterations": 3,
      "max_stagnant_iterations": 1,
      "min_score_delta": 0.01,
      "pass_score": 1.0,
      "max_new_tasks_per_iteration": 12,
      "human_gate": "accept residual risk or release"
    }
  },
  "global_stop_conditions": [
    "all deterministic checks pass and no critical/high finding remains",
    "iteration budget exhausted",
    "score fails to improve by the configured delta",
    "new evidence invalidates approved intent or architecture",
    "an operation crosses the project, network, credential, or deployment boundary"
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
  }
}
