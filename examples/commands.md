# Example Worker Commands

Validate configuration:

```bash
worker config validate
```

Run one cycle:

```bash
worker once
```

Watch continuously:

```bash
worker watch
```

Process one issue directly:

```bash
worker issue --repo your-org/your-repo --issue 42
```

Retry an issue:

```bash
worker retry --repo your-org/your-repo --issue 42
```

Replay a single issue without waiting for watcher polling:

```bash
worker replay --repo your-org/your-repo --issue 42
```

Inspect worker state:

```bash
worker status
worker queue
worker report
worker logs
worker health
```
