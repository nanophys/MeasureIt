"""Shared sweep abstractions and progress tracking helpers."""

from __future__ import annotations

import time
from abc import ABCMeta
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from PyQt5.QtCore import QObject


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


class AbstractSweepMeta(type(QObject), ABCMeta):
    """Metaclass combining QObject's requirements with ABC support."""


class AbstractSweep(QObject, metaclass=AbstractSweepMeta):
    """Base class providing shared state management and progress tracking for sweep-like objects."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.progress_state = ProgressState()
        self.state_at_pause = None
        self.parent_sweep = None
        self.child_sweep = None
        self._accumulated_run_time = 0.0
        self._run_started_at: Optional[float] = None
        self.t0 = 0.0

    @property
    def progressState(self) -> ProgressState:
        """Backward-compatible camelCase alias for progress_state."""
        return self.progress_state

    @progressState.setter
    def progressState(self, value: ProgressState) -> None:
        self.progress_state = value

    def _add_runtime_since_last_resume(self) -> None:
        """Accumulate elapsed run time since the sweep last entered RUNNING."""
        if self._run_started_at is None:
            return
        self._accumulated_run_time += max(time.monotonic() - self._run_started_at, 0.0)
        self._run_started_at = None

    def _enter_running_state(
        self, *, reset_elapsed: bool, state: SweepState = SweepState.RUNNING
    ) -> float:
        """Transition into RUNNING, optionally resetting the accumulated runtime."""
        now = time.monotonic()
        if reset_elapsed:
            self._accumulated_run_time = 0.0
        self._run_started_at = now
        self.progress_state.state = state
        return now

    def is_running(self) -> bool:
        """Determine whether the sweep is currently active."""
        return self.progress_state.state in (SweepState.RUNNING, SweepState.RAMPING)

    def update_progress(self) -> None:
        """Update progress metadata using elapsed time and subclass estimate."""
        total_elapsed = self._accumulated_run_time
        if self._run_started_at is not None:
            total_elapsed += max(time.monotonic() - self._run_started_at, 0.0)
        elapsed_value = total_elapsed

        remaining = self.estimate_time(verbose=False)
        if remaining is None:
            progress_value = 0
        else:
            remaining = self.estimate_time(verbose=False)
            denominator = total_elapsed + remaining
            progress_value = (
                None
                if remaining is None or total_elapsed + remaining <= 0
                else total_elapsed / (total_elapsed + remaining)
            )

        self.progress_state = ProgressState(
            state=self.progress_state.state,
            time_elapsed=elapsed_value,
            time_remaining=remaining,
            progress=progress_value,
        )

    def mark_done(self) -> None:
        """Transition the sweep to DONE and finalize run time tracking."""
        if self.progress_state.state in (SweepState.KILLED, SweepState.DONE):
            return
        if self.progress_state.state == SweepState.RUNNING:
            self._add_runtime_since_last_resume()
        self.progress_state.state = SweepState.DONE

    def estimate_time(self, verbose: bool = False) -> float:
        """Return the estimated time remaining for the sweep."""
        return None

    def start(self, *args, **kwargs):
        """Begin the sweep, resetting timing metadata."""
        if self.progress_state.state in (SweepState.RUNNING, SweepState.RAMPING):
            return None
        run_start = self._enter_running_state(reset_elapsed=True)
        self.progress_state.time_elapsed = 0.0
        self.progress_state.time_remaining = None
        self.progress_state.progress = 0.0
        return run_start

    def pause(self, update_parent=True, update_child=True):
        """Pause the sweep, moving the progress state to PAUSED. If update_parent is True, attempts to pause parent. If update_child is True, may only pause if child sweep successfully pauses."""
        if (
            update_child
            and self.child_sweep is not None
            and not self.child_sweep.pause(False, True)
        ):
            return False
        if self.progress_state.state not in (SweepState.RUNNING, SweepState.RAMPING):
            return False
        if self.progress_state.state == SweepState.RUNNING:
            self._add_runtime_since_last_resume()
        self.state_at_pause = self.progress_state.state
        self.progress_state.state = SweepState.PAUSED
        if update_parent and self.parent_sweep is not None:
            self.parent_sweep.pause(True, False)
        return True

    def stop(self):
        """Stop/pause the sweep. Alias for pause() for backward compatibility."""
        return self.pause()

    def resume(self, update_parent=True, update_child=True):
        """Resume a paused sweep, moving the progress state back to what it was before pausing. If update_parent is True, attempts to resume parent. If update_child is True, may only pause if child sweep successfully resumes."""
        if (
            update_child
            and self.child_sweep is not None
            and not self.child_sweep.resume(False, True)
        ):
            return False
        if self.progress_state.state != SweepState.PAUSED:
            return False
        self._enter_running_state(reset_elapsed=False, state=self.state_at_pause)
        if update_parent and self.parent_sweep is not None:
            self.parent_sweep.resume(True, False)
        return True

    def kill(self, update_parent=True, update_child=True):
        """Terminate the sweep and mark it as killed."""
        if self.progress_state.state == SweepState.RUNNING:
            self._add_runtime_since_last_resume()
        self.progress_state.state = SweepState.KILLED
        if update_parent and self.parent_sweep is not None:
            self.parent_sweep.kill(True, False)
        if update_child and self.child_sweep is not None:
            self.child_sweep.kill(False, True)

    @staticmethod
    def _split_hms(seconds: float) -> tuple[int, int, int]:
        """Convert seconds into hours, minutes, seconds (integer components)."""
        seconds = max(seconds, 0.0)
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(round(seconds % 60))
        if secs == 60:
            secs = 0
            minutes += 1
        if minutes == 60:
            minutes = 0
            hours += 1
        return hours, minutes, secs


__all__ = ["AbstractSweep", "ProgressState", "SweepState"]
