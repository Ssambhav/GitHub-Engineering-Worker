# Memory Schemas

Schema templates for memory objects live here. They are declarative YAML examples that future runtime code can translate into JSON Schema, OpenAPI, Pydantic, TypeScript, or another validation format.

## Files

- [memory-envelope.schema.yaml](memory-envelope.schema.yaml): common envelope used by all authoritative memory objects.
- [canonical-objects.schema.yaml](canonical-objects.schema.yaml): canonical object family payload templates.
- [memory-mutation.schema.yaml](memory-mutation.schema.yaml): mutation record template.
- [memory-relationship.schema.yaml](memory-relationship.schema.yaml): relationship and evidence reference template.

No storage or validation runtime is implemented here.
