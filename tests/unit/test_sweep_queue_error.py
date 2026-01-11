# test_sweep_queue_error.py
"""Test that SweepQueue properly stops when a Sweep2D fails."""

import pytest
import time
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import QApplication

from measureit.sweep.sweep2d import Sweep2D
from measureit.sweep.progress import SweepState
from measureit.tools.sweep_queue import SweepQueue
from tests.fixtures.mock_instruments import MockMagnet, MockGate, MockLockIn


@pytest.fixture(scope="module")
def qt_app():
    """Create a QApplication for the test module."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_magnet():
    """Create a mock magnet that fails above B=7.8 T."""
    magnet = MockMagnet("mock_magnet_queue", fail_above=7.8)
    yield magnet
    magnet.close()


@pytest.fixture
def mock_gate():
    """Create a mock gate voltage source."""
    gate = MockGate("mock_gate_queue")
    yield gate
    gate.close()


@pytest.fixture
def mock_lockin():
    """Create a mock lock-in amplifier."""
    lockin = MockLockIn("mock_lockin_queue")
    yield lockin
    lockin.close()


class TestSweepQueueError:
    """Test suite for SweepQueue error handling when Sweep2D fails."""

    def test_sweep_queue_stops_on_sweep2d_error(
        self, qt_app, mock_magnet, mock_gate, mock_lockin
    ):
        """
        Verify that SweepQueue stops when a Sweep2D enters ERROR state.

        This tests the full integration:
        1. Sweep2D with inner sweep that will fail
        2. Error propagates correctly (inner -> outer)
        3. Sweep2D stays in ERROR state (not overwritten by DONE)
        4. SweepQueue detects ERROR and stops the queue
        """
        # Create first sweep that will fail
        sweep1 = Sweep2D(
            [mock_magnet.B, 0.0, 8.0, 1.0],  # Inner: B, will fail at 8.0
            [mock_gate.Vtg, 0.0, 1.0, 0.5],  # Outer: Vtg
            inter_delay=0.001,
            outer_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        sweep1.follow_param(mock_lockin.x)

        # Create second sweep that should NOT run
        sweep2 = Sweep2D(
            [mock_magnet.B, 0.0, 1.0, 0.5],
            [mock_gate.Vtg, 0.0, 0.5, 0.25],
            inter_delay=0.001,
            outer_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        sweep2.follow_param(mock_lockin.x)

        # Create queue
        queue = SweepQueue(inter_delay=0.1)
        queue.append(sweep1, sweep2)

        # Track if sweep2 was started
        sweep2_started = [False]
        original_start = sweep2.start

        def track_start(*args, **kwargs):
            sweep2_started[0] = True
            return original_start(*args, **kwargs)

        sweep2.start = track_start

        # Start the queue
        queue.start(rts=False)

        # Wait for queue to finish or error
        timeout = 30
        start_time = time.time()
        while queue.current_sweep is not None and queue.current_sweep.progressState.state == SweepState.RUNNING:
            QCoreApplication.processEvents()
            time.sleep(0.01)
            if time.time() - start_time > timeout:
                queue.kill()
                pytest.fail("Queue timed out")

        # Process remaining events
        for _ in range(20):
            QCoreApplication.processEvents()
            time.sleep(0.01)

        # Verify sweep1 is in ERROR state
        assert sweep1.progressState.state == SweepState.ERROR, (
            f"sweep1 should be in ERROR state, got {sweep1.progressState.state}"
        )

        # Verify sweep2 was NOT started (queue stopped on error)
        assert not sweep2_started[0], (
            "sweep2 should NOT have been started - queue should stop on error"
        )

        # Verify queue has remaining items (sweep2 was not processed)
        assert len(queue.queue) == 1, (
            f"Queue should have 1 remaining item (sweep2), got {len(queue.queue)}"
        )

        # Clean up
        sweep1.kill()
        sweep2.kill()

    def test_sweep_queue_detects_error_state(
        self, qt_app, mock_magnet, mock_gate, mock_lockin
    ):
        """
        Unit test: Verify that SweepQueue's begin_next() correctly detects ERROR state.
        """
        sweep = Sweep2D(
            [mock_magnet.B, 0.0, 1.0, 0.1],
            [mock_gate.Vtg, 0.0, 1.0, 0.1],
            inter_delay=0.01,
            outer_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        sweep.follow_param(mock_lockin.x)

        queue = SweepQueue(inter_delay=0.1)
        queue.append(sweep)

        # Manually set sweep to ERROR state (simulating what happens after our fix)
        queue.current_action = sweep
        queue.current_sweep = sweep
        sweep.progressState.state = SweepState.ERROR
        sweep.progressState.error_message = "Test error"

        # Call begin_next (what happens when sweep completes)
        queue.begin_next()

        # Process events
        for _ in range(5):
            QCoreApplication.processEvents()
            time.sleep(0.01)

        # Verify queue stopped (current_sweep should be None after cleanup)
        assert queue.current_sweep is None, (
            "Queue should have cleaned up current_sweep on error"
        )

        # Clean up
        sweep.kill()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
