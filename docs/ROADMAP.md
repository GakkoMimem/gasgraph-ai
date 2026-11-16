# Roadmap — meaningful next iterations

### Next: richer knowledge representation

- Entity attributes with time-dependent states, typed relations beyond `FLOWS_TO` and explicit containment hierarchies.
- Time-dependent dependency logic and edge-specific schedules.
- More formal ontology modeling and import/export formats.

### Next: better agent interoperability

- End-to-end MCP Inspector tests against a pinned SDK release.
- Run the optional local planner with an actual supported LM Studio model and document tool-call reliability.
- Add evidence-bound language generation and clearer no-answer behavior for ambiguous questions.

### Next: stronger engineering realism (still synthetic)

- Extend the graph to a small mathematical flow model with capacity constraints, preserving clear warnings that it is not a physical simulation.
- Compare planned work schedules and introduce objective-weighted scenario ranking.
- More rigorous versioning and trace IDs for changes to synthetic data.

### Before any operational backend deployment

- Authentication, authorization, anti-CSRF protection, secure session storage, rate limiting, auditing, threat modeling and architecture review.
- Data governance and explicit enterprise approval workflows. No direct control or real-world operational actions.

> The browser-only public demo uses synthetic data and no privileged operations. A connected operational service would require the security and governance controls above.
