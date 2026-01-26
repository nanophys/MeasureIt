"""Test to verify SweepQueue status stays 'running' during Sweep2D execution.

This test verifies the fix for the bug where sweep_queue.status() would report
"pending" in the middle of running a sequence of Sweep2D sweeps.

The fix adds a `_is_running` flag that is set when start() is called and cleared
when the queue finishes, is killed, or encounters an error.
"""

from __future__ import annotations

import os
from functools import partial
from typing import Any, Callable, Optional

import pytest

os.environ.setdefault("MEASUREIT_FAKE_QT", "1")

from measureit.tools import sweep_queue as sq
from measureit.sweep.progress import SweepState


class DummySignal:
    """Minimal replacement for a Qt signal."""

    def __init__(self) -> None:
        self._slots: list[Callable[..., None]] = []

    def connect(self, slot: Callable[..., None]) -> None:
        self._slots.append(slot)

    def disconnect(self, slot: Callable[..., None]) -> None:
        try:
            self._slots.remove(slot)
        except ValueError:
            pass

    def emit(self, *args: Any, **kwargs: Any) -> None:
        for slot in list(self._slots):
            slot(*args, **kwargs)


class DummySweep2D:
    """Lightweight stand-in for Sweep2D that simulates state transitions."""

    def __init__(self, name: str, save_data: bool = True) -> None:
        self.name = name
        self.save_data = save_data
        self.started: bool = False
        self.killed: int = 0
        self.resumed: int = 0
        self.metadata_provider = None
        self.progressState = type("State", (), {
            "state": SweepState.READY,
            "is_queued": False,
            "error_message": None,
        })()
        self.completed = DummySignal()
        self._complete_func: Optional[Callable[[], None]] = None

        # Sweep2D specific attributes
        self.set_param = type("Param", (), {"label": f"{name}-outer", "unit": "V"})()
        self.out_start = 0.0
        self.out_stop = 1.0
        self.begin = self.out_start
        self.end = self.out_stop

    def set_complete_func(self, func: Callable[..., None], *args: Any, **kwargs: Any) -> None:
        callback = partial(func, *args, **kwargs)
        self._complete_func = callback
        self.completed.connect(callback)

    def start(self, persist_data: Any = None, ramp_to_start: bool = True) -> None:
        """Simulate Sweep2D.start() - goes through READY -> RAMPING -> READY -> RUNNING."""
        self.started = True
        # Simulate ramp transition (brief READY state after ramping)
        self.progressState.state = SweepState.RAMPING
        self.progressState.state = SweepState.READY  # Brief transition
        self.progressState.state = SweepState.RUNNING

    def kill(self) -> None:
        self.killed += 1
        self.progressState.state = SweepState.KILLED

    def resume(self) -> None:
        self.resumed += 1
        self.progressState.state = SweepState.RUNNING

    def pause(self) -> None:
        self.progressState.state = SweepState.PAUSED

    def export_json(self, fn: Optional[str] = None) -> dict[str, Any]:
        return {
            "module": "tests.stub",
            "class": "DummySweep2D",
            "attributes": {"name": self.name, "save_data": self.save_data},
        }

    def trigger_complete(self) -> None:
        """Simulate the sweep finishing and emitting its completed signal."""
        self.progressState.state = SweepState.DONE
        self.completed.emit()

    def __repr__(self) -> str:
        return f"<DummySweep2D {self.name}>"


class DummySweep1D:
    """Minimal Sweep1D for type checking."""
    pass


class DummySweep0D:
    """Minimal Sweep0D for type checking."""
    pass


class DummySimulSweep:
    """Minimal SimulSweep for type checking."""
    pass


@pytest.fixture(autouse=True)
def stub_sweep_types(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace SweepQueue's sweep types with lightweight stubs for every test."""
    monkeypatch.setattr(sq, "BaseSweep", DummySweep2D)
    monkeypatch.setattr(sq, "Sweep1D", DummySweep1D)
    monkeypatch.setattr(sq, "Sweep0D", DummySweep0D)
    monkeypatch.setattr(sq, "SimulSweep", DummySimulSweep)


@pytest.fixture
def queue() -> sq.SweepQueue:
    queue = sq.SweepQueue(inter_delay=0.0, post_db_delay=0.0, debug=True)
    queue.newSweepSignal = DummySignal()
    yield queue
    try:
        queue.kill()
    finally:
        queue.queue.clear()


def test_status_pending_only_before_start(queue: sq.SweepQueue) -> None:
    """Test that status is 'pending' only when queue has items but hasn't started."""
    sweep1 = DummySweep2D("sweep2d_1", save_data=True)
    sweep2 = DummySweep2D("sweep2d_2", save_data=True)

    queue.append(sweep1, sweep2)

    # Before start(), status should be "pending"
    status = queue.status()
    assert status["effective_state"] == "pending", \
        f"Expected 'pending' before start, got {status['effective_state']}"
    assert queue._is_running is False


def test_status_running_throughout_execution(queue: sq.SweepQueue) -> None:
    """Test that status stays 'running' throughout sweep execution.

    This is the main test for the reported bug: status should be 'running'
    during all transitions between sweeps, not 'pending'.
    """
    sweep1 = DummySweep2D("sweep2d_1", save_data=True)
    sweep2 = DummySweep2D("sweep2d_2", save_data=True)
    sweep3 = DummySweep2D("sweep2d_3", save_data=True)

    queue.append(sweep1, sweep2, sweep3)
    queue.start()

    # After start(), _is_running should be True and status should be "running"
    assert queue._is_running is True
    status1 = queue.status()
    assert status1["effective_state"] == "running", \
        f"Expected 'running' after start, got {status1['effective_state']}"

    # Simulate mid-sweep state where sweep is in READY (brief transition)
    sweep1.progressState.state = SweepState.READY
    status_during_ready = queue.status()
    assert status_during_ready["effective_state"] == "running", \
        f"Expected 'running' even during READY state, got {status_during_ready['effective_state']}"

    # Complete first sweep
    sweep1.trigger_complete()

    # Status should still be "running" (queue is processing)
    status2 = queue.status()
    assert status2["effective_state"] == "running", \
        f"Expected 'running' after first sweep complete, got {status2['effective_state']}"

    # Even if the new sweep is in READY state (before start() is called on it)
    sweep2.progressState.state = SweepState.READY
    status_transition = queue.status()
    assert status_transition["effective_state"] == "running", \
        f"Expected 'running' during transition, got {status_transition['effective_state']}"


def test_status_running_with_database_entries(queue: sq.SweepQueue, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that status stays 'running' when processing DatabaseEntry items."""
    from measureit.tools.sweep_queue import DatabaseEntry

    class MockDatabaseEntry(DatabaseEntry):
        """Mock DatabaseEntry that inherits from the real class."""
        def __init__(self):
            self.started = False
            # Don't call super().__init__() to avoid database setup

        def start(self):
            self.started = True

        def __str__(self):
            return "MockDatabaseEntry"

    # Patch DatabaseEntry in the module so isinstance checks work
    monkeypatch.setattr(sq, "DatabaseEntry", MockDatabaseEntry)

    db = MockDatabaseEntry()
    sweep = DummySweep2D("sweep2d_1", save_data=True)

    # Manually add to queue
    queue.queue.append(db)
    sweep.set_complete_func(queue.begin_next)
    sweep.progressState.is_queued = True
    queue.queue.append(sweep)

    queue.start()

    # After start() processes DatabaseEntry and moves to sweep, should be running
    assert queue._is_running is True
    assert db.started is True  # Verify DatabaseEntry was actually processed


def test_status_idle_after_all_complete(queue: sq.SweepQueue) -> None:
    """Test that status is 'idle' after all sweeps complete."""
    sweep1 = DummySweep2D("sweep2d_1", save_data=True)

    queue.append(sweep1)
    queue.start()

    assert queue._is_running is True

    # Complete the sweep
    sweep1.trigger_complete()

    # After all work is done, status should be "idle"
    assert queue._is_running is False
    status = queue.status()
    assert status["effective_state"] == "idle", \
        f"Expected 'idle' after all complete, got {status['effective_state']}"


def test_status_killed_after_kill(queue: sq.SweepQueue) -> None:
    """Test that status is 'killed' after kill() is called."""
    sweep1 = DummySweep2D("sweep2d_1", save_data=True)
    sweep2 = DummySweep2D("sweep2d_2", save_data=True)

    queue.append(sweep1, sweep2)
    queue.start()

    assert queue._is_running is True

    queue.kill()

    assert queue._is_running is False
    status = queue.status()
    assert status["effective_state"] == "killed", \
        f"Expected 'killed' after kill, got {status['effective_state']}"


def test_status_running_after_restart(queue: sq.SweepQueue) -> None:
    """Test that status becomes 'running' when restarting after kill."""
    sweep1 = DummySweep2D("sweep2d_1", save_data=True)
    sweep2 = DummySweep2D("sweep2d_2", save_data=True)

    queue.append(sweep1, sweep2)
    queue.start()
    queue.kill()

    assert queue._is_running is False

    # Restart with remaining item
    queue.start()

    assert queue._is_running is True
    status = queue.status()
    assert status["effective_state"] == "running", \
        f"Expected 'running' after restart, got {status['effective_state']}"


def test_status_paused_when_sweep_paused(queue: sq.SweepQueue) -> None:
    """Test that status is 'paused' when current sweep is paused."""
    sweep = DummySweep2D("sweep2d_1", save_data=True)
    queue.append(sweep)
    queue.start()

    # Pause the sweep
    sweep.pause()

    status = queue.status()
    assert status["effective_state"] == "paused", \
        f"Expected 'paused' when sweep paused, got {status['effective_state']}"


def test_status_stopped_after_callable_error(queue: sq.SweepQueue) -> None:
    """Test that status is 'stopped' when a callable in start() raises an error."""
    def error_callable():
        raise ValueError("Test error")

    queue.queue.append(error_callable)
    queue.start()

    # After callable error, _is_running should be False and status should be "stopped"
    assert queue._is_running is False
    status = queue.status()
    assert status["effective_state"] == "stopped", \
        f"Expected 'stopped' after callable error, got {status['effective_state']}"
    assert status["last_error"] is not None


def test_status_stopped_after_invalid_action(queue: sq.SweepQueue) -> None:
    """Test that status is 'stopped' when an invalid action is in the queue."""
    # Add an object that is neither a sweep, DatabaseEntry, nor callable
    invalid_action = object()
    queue.queue.append(invalid_action)
    queue.start()

    # After invalid action, _is_running should be False and status should be "stopped"
    assert queue._is_running is False
    status = queue.status()
    assert status["effective_state"] == "stopped", \
        f"Expected 'stopped' after invalid action, got {status['effective_state']}"
    assert status["last_error"] is not None
    assert "Invalid action" in status["last_error"]["message"]


def test_clear_error_does_not_make_running(queue: sq.SweepQueue) -> None:
    """Test that clear_error() doesn't make status report 'running' when nothing is executing."""
    def error_callable():
        raise ValueError("Test error")

    queue.queue.append(error_callable)
    queue.start()

    assert queue._is_running is False
    assert queue.status()["effective_state"] == "stopped"

    # Clear the error
    queue.clear_error()

    # Status should be "idle", not "running"
    assert queue._is_running is False
    status = queue.status()
    assert status["effective_state"] == "idle", \
        f"Expected 'idle' after clear_error, got {status['effective_state']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
