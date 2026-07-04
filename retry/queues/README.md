# Retry Queues

Pending retry records belong here when local retry persistence is enabled by future runtime code.

Runtime queue contents are ignored by Git.

Queue entries must reference retry attempt records, recovery plans, state snapshots, and audit refs. They must not contain raw secrets, full repository files, oversized logs, or executable retry logic.
