# Memory Subsystem

This directory contains the declarative architecture, contracts, schemas, and scaffolding for the GitHub Engineering Worker memory subsystem.

Memory is structured execution knowledge. It is not chat history, raw logs, or a hidden transcript. Runtime storage, retrieval, indexing, and compaction logic are intentionally out of scope for this repository phase.

## Contents

- [MEMORY.md](MEMORY.md): canonical memory architecture.
- [schemas/](schemas/): schema templates for memory envelopes and canonical object families.
- [contracts/](contracts/): reusable contracts for memory objects and access operations.
- [interfaces/](interfaces/): interface definitions future runtime code may implement.
- [checkpoints/](checkpoints/): checkpoint manifest templates and restoration contracts.
- [snapshots/](snapshots/): snapshot manifest templates.
- [history/](history/): version, mutation, and timeline templates.
- [configuration/](configuration/): policy and retention configuration templates.
- [daily/](daily/): placeholder for future curated daily operational memories.
- [episodic/](episodic/): placeholder for workflow episode memories.
- [semantic/](semantic/): placeholder for distilled semantic knowledge.
- [long-term/](long-term/): placeholder for curated persistent memory.

## Boundaries

Do not add database code, storage engines, retrieval services, runtime agents, or tool implementations here. This subsystem defines contracts and extension points only.
