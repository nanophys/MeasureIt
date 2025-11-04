"""Shared progress-tracking primitives for MeasureIt sweeps."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SweepState(Enum):
    READY = "ready"
    RAMPING = "ramping"
    RUNNING = "running"
    PAUSED = "paused"
    DONE = "done"
    KILLED = "killed"


@dataclass
class ProgressState:
    """Lightweight container tracking sweep progress."""

    state: SweepState = SweepState.READY
    time_elapsed: Optional[float] = None
    time_remaining: Optional[float] = None
    progress: Optional[float] = None


__all__ = ["ProgressState", "SweepState"]
