# Dead Letter Queue

Failed work items that exceeded retry policy belong here when future runtime code enables local persistence.

Dead-letter records should contain escalation reports, terminal retry outcomes, state snapshot refs, audit refs, and cleanup obligations. They should not contain raw secrets, full repository files, or runnable recovery code.
