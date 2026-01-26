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
    ERROR = "error"


@dataclass
class ProgressState:
    """Lightweight container tracking sweep progress.

    Attributes
    ----------
    state : SweepState
        Current state of the sweep (READY, RAMPING, RUNNING, PAUSED, DONE, KILLED, ERROR).
    time_elapsed : float, optional
        Time elapsed since sweep started, in seconds.
    time_remaining : float, optional
        Estimated time remaining, in seconds.
    progress : float, optional
        Progress percentage (0.0 to 1.0).
    error_message : str, optional
        Error message if sweep ended in ERROR state.
    error_count : int
        Number of errors encountered during sweep execution.
    is_queued : bool
        True if the sweep is managed by a SweepQueue (either waiting in queue or
        currently running as part of queue execution). This allows external tools
        to distinguish between a sweep that is idle (not yet started) vs one that
        is part of a queue workflow. Set to True when appended to a SweepQueue,
        and False when the sweep completes, is killed, or is removed from the queue.
    """

    state: SweepState = SweepState.READY
    time_elapsed: Optional[float] = None
    time_remaining: Optional[float] = None
    progress: Optional[float] = None
    error_message: Optional[str] = None
    error_count: int = 0
    is_queued: bool = False


__all__ = ["ProgressState", "SweepState"]
