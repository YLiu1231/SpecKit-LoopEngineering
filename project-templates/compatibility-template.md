# Compatibility and recovery: [FEATURE]

## Scope

List affected APIs, events, shared data, SDK/configuration, business semantics, errors and timing.
Reference `boundary-review.json`, target dependencies, contracts and an explicit support window.

## Version matrix

| Producer | Consumer | Required behavior | Case IDs |
| --- | --- | --- | --- |
| Old | Old | Production baseline | [IDs] |
| New | Old | Existing consumers remain supported | [IDs] |
| Old | New | Old business preserved; new capability explicitly degraded | [IDs] |
| New | New | Complete new behavior | [IDs] |

When the local project is the consumer, map local/peer version labels explicitly; do not reverse semantics.
Describe data, message and configuration compatibility, independent rollback and its limitations.
Restricted rollback requires a scoped developer decision and an alternative recovery path.
Approval does not prove a recovery drill occurred. Preserve unknowns and case execution gaps.

## No external change

[If applicable, give evidence-backed reason instead of inventing a matrix.]
