schema_version: "1.0"
workflow:
  id: "loop-engineering"
  name: "Bounded Four-Loop Engineering"
  version: "1.0.0"
  author: "Local Agent Harness"
  description: "Runs four bounded evaluator-optimizer loops with only intent and architecture gates"

requires:
  speckit_version: ">=0.13.0"
  integrations:
    any:
      - "claude"

inputs:
  spec:
    type: string
    required: true
    prompt: "Describe what you want to build"
  integration:
    type: string
    default: "claude"
    enum:
      - "claude"

steps:
  - id: requirements-loop
    command: loop.requirements
    integration: "{{ inputs.integration }}"
    input:
      args: "{{ inputs.spec }}"

  - id: intent-gate
    type: gate
    message: "Approve product intent: scope, user-visible behavior, security/privacy assumptions, exclusions, and measurable success. This approval is for the requirements baseline, not individual commands."
    options: [approve, reject]
    on_reject: abort

  - id: design-loop
    command: loop.design
    integration: "{{ inputs.integration }}"
    input:
      args: "Design only within the approved requirements baseline."

  - id: architecture-gate
    type: gate
    message: "Approve the execution baseline: architecture, dependencies, data changes, security boundary, test evidence, and rollback. This approval authorizes project-local implementation inside the configured platform boundary."
    options: [approve, reject]
    on_reject: abort

  - id: implementation-loop
    command: loop.implementation
    integration: "{{ inputs.integration }}"
    input:
      args: "Implement the approved plan in the smallest independently testable slices."

  - id: convergence-loop
    command: loop.convergence
    integration: "{{ inputs.integration }}"
    input:
      args: "Converge only within approved scope; do not deploy, publish, push, or merge."
