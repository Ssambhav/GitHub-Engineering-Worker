# State Transitions

Declarative transition graph and transition rule catalog.

- `transition-graph.yaml` lists legal primary-state edges.
- `transition-rules.yaml` defines generic preconditions, postconditions, failure handling, and transition classes.

The graph is authoritative for legality. Runtime code, when added later, must validate against it rather than infer transitions.
