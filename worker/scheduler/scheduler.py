"""Configurable stdlib scheduler for worker polling."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timedelta

from runtime.models.common import CancellationToken
from worker.configuration import ScheduleMode, WorkerConfiguration


class WorkerScheduler:
    """Runs a worker callback in once, manual, interval, watch, or simple cron mode."""

    def __init__(self, config: WorkerConfiguration, cancellation_token: CancellationToken | None = None) -> None:
        self.config = config
        self.cancellation_token = cancellation_token or CancellationToken()

    def run(self, callback: Callable[[], None]) -> None:
        if self.config.mode in {ScheduleMode.ONCE, ScheduleMode.MANUAL}:
            callback()
            return
        while not self.cancellation_token.is_cancelled:
            callback()
            self._sleep_until_next()

    def _sleep_until_next(self) -> None:
        delay = self._next_delay_seconds()
        deadline = time.monotonic() + delay
        while time.monotonic() < deadline:
            if self.cancellation_token.is_cancelled:
                return
            time.sleep(min(1.0, deadline - time.monotonic()))

    def _next_delay_seconds(self) -> float:
        if self.config.mode == ScheduleMode.CRON and self.config.cron:
            return max(1.0, _cron_delay_seconds(self.config.cron))
        return max(1.0, self.config.poll_interval.total_seconds())


def _cron_delay_seconds(expression: str) -> float:
    """Support common five-field minute cron expressions for polling."""

    fields = expression.split()
    if len(fields) != 5:
        raise ValueError(f"unsupported cron expression: {expression}")
    minute = fields[0]
    now = datetime.now()
    if minute.startswith("*/"):
        step = int(minute[2:])
        next_minute = ((now.minute // step) + 1) * step
        next_time = now.replace(second=0, microsecond=0)
        if next_minute >= 60:
            next_time = (next_time.replace(minute=0) + timedelta(hours=1))
        else:
            next_time = next_time.replace(minute=next_minute)
        return (next_time - now).total_seconds()
    if minute == "*":
        return 60 - now.second
    target = int(minute)
    next_time = now.replace(minute=target, second=0, microsecond=0)
    if next_time <= now:
        next_time += timedelta(hours=1)
    return (next_time - now).total_seconds()
