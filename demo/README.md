# Demo

This folder contains a runnable local demonstration of the final worker lifecycle. It does not require GitHub or AI credentials. The demo uses mock controller dependencies where needed and shows both a successful pull request dry run and an escalation path.

Run:

```bash
python scripts/demo_worker.py
```

Expected output:

```text
SUCCESS FLOW
Issue -> Repository -> Worker -> Patch -> Tests -> Pull Request
Status: dry_run_pr_created

FAILURE FLOW
Issue -> Three failed attempts -> Confidence drops -> Escalation
Status: failed
```
