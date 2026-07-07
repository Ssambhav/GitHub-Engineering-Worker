"""Command line interface for the autonomous worker."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from runtime.configuration.environment import load_environment
from worker.configuration import ScheduleMode, WorkerConfigurationLoader
from worker.daemon import WorkerDaemon
from worker.daemon.daemon import read_status
from worker.models import WorkerIssue, WorkerPaths


def main(argv: list[str] | None = None) -> int:
    load_environment()
    parser = argparse.ArgumentParser(prog="worker")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run")
    sub.add_parser("watch")
    sub.add_parser("once")
    issue_parser = sub.add_parser("issue")
    issue_parser.add_argument("--repo", required=True)
    issue_parser.add_argument("--issue", type=int, required=True)
    retry_parser = sub.add_parser("retry")
    retry_parser.add_argument("--repo", required=True)
    retry_parser.add_argument("--issue", type=int, required=True)
    replay_parser = sub.add_parser("replay")
    replay_parser.add_argument("--repo", required=True)
    replay_parser.add_argument("--issue", type=int, required=True)
    report_parser = sub.add_parser("report")
    report_parser.add_argument("--execution-id")
    sub.add_parser("queue")
    sub.add_parser("logs")
    sub.add_parser("status")
    sub.add_parser("health")
    config_parser = sub.add_parser("config")
    config_sub = config_parser.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("validate")
    args = parser.parse_args(argv)

    if args.command == "status":
        _, config = WorkerConfigurationLoader().load()
        print(json.dumps(read_status(config.status_path), indent=2, sort_keys=True))
        return 0

    daemon = WorkerDaemon()
    if args.command == "run":
        daemon.run()
        return 0
    if args.command == "watch":
        daemon.run(mode=ScheduleMode.WATCH)
        return 0
    if args.command == "once":
        daemon.run(mode=ScheduleMode.ONCE)
        return 0
    if args.command == "issue":
        daemon.initialize()
        added = daemon.enqueue_issue(WorkerIssue(repository=args.repo, number=args.issue))
        daemon.tick()
        print("enqueued" if added else "duplicate")
        return 0
    if args.command == "retry":
        daemon.initialize()
        added = daemon.enqueue_issue(WorkerIssue(repository=args.repo, number=args.issue, attempts=1))
        daemon.tick()
        print("retry enqueued" if added else "duplicate")
        return 0
    if args.command == "replay":
        daemon.initialize()
        issue = WorkerIssue(repository=args.repo, number=args.issue)
        result = daemon._execute_issue(issue)
        print(getattr(result, "status", "completed"))
        return 0
    if args.command == "report":
        _, config = WorkerConfigurationLoader().load()
        reports = sorted(config.decisions.report_directory.glob("*.json")) if config.decisions.report_directory.exists() else []
        if args.execution_id:
            reports = [path for path in reports if path.stem == args.execution_id]
        for path in reports:
            print(path)
        return 0
    if args.command == "queue":
        _, config = WorkerConfigurationLoader().load()
        from worker.queue import PersistentIssueQueue

        queue = PersistentIssueQueue(config.queue_persistence)
        for key in queue.keys():
            print(key)
        return 0
    if args.command == "logs":
        _, config = WorkerConfigurationLoader().load()
        audit_path = config.decisions.audit_directory / "audit.jsonl"
        if audit_path.exists():
            print(audit_path.read_text(encoding="utf-8"))
        return 0
    if args.command == "health":
        daemon.initialize()
        for check in daemon.health().startup_validation():
            print(f"{check.name}: {'ok' if check.healthy else 'fail'} - {check.message}")
        return 0
    if args.command == "config" and args.config_command == "validate":
        _, config = WorkerConfigurationLoader().load()
        errors = config.validate()
        if errors:
            for error in errors:
                print(f"error: {error}")
            return 1
        print("configuration is valid")
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
