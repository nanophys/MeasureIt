"""Focused unit tests for SweepQueue using lightweight stubs.

These tests avoid creating real sweep objects (which pull in heavy PyQt/QCoDeS
state) by monkeypatching the sweep types that SweepQueue depends upon. This
lets us exercise the queue orchestration logic without triggering native
shutdown crashes observed with the full GUI stack.
"""

from __future__ import annotations

import os
from functools import partial
from typing import Any, Callable, List, Optional

import pytest

os.environ.setdefault("MEASUREIT_FAKE_QT", "1")

from measureit.tools import sweep_queue as sq


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


class DummySweep:
    """Lightweight stand-in for BaseSweep and its subclasses."""

    def __init__(
        self,
        name: str,
        sweep_kind: str = "generic",
        start_value: float = 0.0,
        end_value: float = 1.0,
    ) -> None:
        self.name = name
        self.started: bool = False
        self.killed: int = 0
        self.resumed: int = 0
        self.metadata_provider = None
        self.progressState = type("State", (), {"state": "READY"})()
        self.completed = DummySignal()
        self._complete_func: Optional[Callable[[], None]] = None
        self.begin = start_value
        self.end = end_value
        self.max_time = 2.0
        self.sweep_kind = sweep_kind
        self.set_param = type(
            "Param",
            (),
            {"label": f"{name}-param", "unit": "V"},
        )()
        self.export_payload = {
            "module": "tests.stub",
            "class": f"Dummy{sweep_kind.title()}",
            "attributes": {"name": name},
        }

    # --- API expected by SweepQueue -------------------------------------------------

    def set_complete_func(self, func: Callable[..., None], *args: Any, **kwargs: Any) -> None:
        callback = partial(func, *args, **kwargs)
        self._complete_func = callback
        self.completed.connect(callback)

    def start(self, persist_data: Any = None, ramp_to_start: bool = False) -> None:
        self.started = True
        self.progressState.state = "RUNNING"

    def kill(self) -> None:
        self.killed += 1
        self.progressState.state = "KILLED"

    def resume(self) -> None:
        self.resumed += 1
        self.progressState.state = "RUNNING"

    def export_json(self, fn: Optional[str] = None) -> dict[str, Any]:
        return dict(self.export_payload)

    # --- Helpers for the tests ------------------------------------------------------

    def trigger_complete(self) -> None:
        """Simulate the sweep finishing and emitting its completed signal."""
        self.progressState.state = "DONE"
        self.completed.emit()

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<DummySweep {self.name}>"


class DummySweep1D(DummySweep):
    def __init__(self, name: str) -> None:
        super().__init__(name, sweep_kind="1d")


class DummySweep0D(DummySweep):
    def __init__(self, name: str, duration: float) -> None:
        super().__init__(name, sweep_kind="0d")
        self.max_time = duration


class DummySimulSweep(DummySweep):
    def __init__(self, name: str) -> None:
        super().__init__(name, sweep_kind="simul")


class DummyDatabaseEntry:
    """Simplified DatabaseEntry replacement."""

    def __init__(self, label: str = "db") -> None:
        self.label = label
        self.started: bool = False

    def start(self) -> None:
        self.started = True

    def __str__(self) -> str:  # pragma: no cover - logging helper
        return f"DummyDatabaseEntry<{self.label}>"


@pytest.fixture(autouse=True)
def stub_sweep_types(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace SweepQueue's sweep types with lightweight stubs for every test."""

    monkeypatch.setattr(sq, "BaseSweep", DummySweep)
    monkeypatch.setattr(sq, "Sweep1D", DummySweep1D)
    monkeypatch.setattr(sq, "Sweep0D", DummySweep0D)
    monkeypatch.setattr(sq, "SimulSweep", DummySimulSweep)
    monkeypatch.setattr(sq, "DatabaseEntry", DummyDatabaseEntry)

    # Dispatch callables synchronously – no Qt/asyncio event loop required.
    monkeypatch.setattr(sq.SweepQueue, "_exec_in_kernel", lambda self, fn: fn())


@pytest.fixture
def queue() -> sq.SweepQueue:
    queue = sq.SweepQueue(inter_delay=0.0, post_db_delay=0.0, debug=True)
    queue.newSweepSignal = DummySignal()
    yield queue
    try:
        queue.kill()
    finally:
        queue.queue.clear()


def test_append_registers_completion(queue: sq.SweepQueue) -> None:
    sweep = DummySweep("alpha")

    queue.append(sweep)

    assert list(queue) == [sweep]
    assert sweep._complete_func is not None


def test_start_processes_sweeps_in_order(queue: sq.SweepQueue) -> None:
    first = DummySweep1D("first")
    second = DummySweep("second")

    queue.append(first, second)
    queue.start()

    assert queue.current_sweep is first
    assert first.started is True
    assert second.started is False

    first.trigger_complete()  # Should advance to the next sweep
    assert queue.current_sweep is second
    assert second.started is True

    second.trigger_complete()
    assert queue.current_sweep is None
    assert not queue.queue  # Queue drained
    assert first.killed == 1  # Sweeps are killed when finished
    assert second.killed == 1


def test_queue_handles_database_entries_and_callables(queue: sq.SweepQueue) -> None:
    db = DummyDatabaseEntry("primary")
    log: List[str] = []

    def callback() -> None:
        log.append("callback-run")

    sweep = DummySweep("omega")

    queue.append(db, sweep)
    queue.append_handle(callback)
    queue.start()

    assert db.started is True  # Database entry executed before sweep
    assert queue.current_sweep is sweep

    sweep.trigger_complete()
    assert log == ["callback-run"]
    assert queue.current_sweep is None


def test_queue_reordering_helpers(queue: sq.SweepQueue) -> None:
    sweeps = [DummySweep(f"s{i}") for i in range(3)]
    queue.append(*sweeps)

    queue.move(sweeps[0], 2)
    assert list(queue) == [sweeps[1], sweeps[2], sweeps[0]]

    replacement = DummySweep("replacement")
    queue.replace(1, replacement)
    assert list(queue)[1] is replacement

    queue.delete(replacement)
    assert replacement not in queue


def test_export_json_includes_queue_configuration(queue: sq.SweepQueue) -> None:
    queue.append(DummySweep("json-test"))

    data = queue.export_json()

    assert data["inter_delay"] == queue.inter_delay
    assert isinstance(data["queue"], list)
    assert data["queue"][0]["attributes"]["name"] == "json-test"
