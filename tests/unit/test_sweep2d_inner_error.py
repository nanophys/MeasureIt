# test_sweep2d_inner_error.py
"""Test that Sweep2D properly enters ERROR state when inner Sweep1D fails."""

import pytest
import time
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import QApplication

from measureit.sweep.sweep2d import Sweep2D
from measureit.sweep.progress import SweepState
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
    magnet = MockMagnet("mock_magnet", fail_above=7.8)
    yield magnet
    magnet.close()


@pytest.fixture
def mock_gate():
    """Create a mock gate voltage source."""
    gate = MockGate("mock_gate")
    yield gate
    gate.close()


@pytest.fixture
def mock_lockin():
    """Create a mock lock-in amplifier."""
    lockin = MockLockIn("mock_lockin")
    yield lockin
    lockin.close()


class TestSweep2DInnerError:
    """Test suite for Sweep2D error handling when inner sweep fails."""

    def test_sweep2d_enters_error_state_when_inner_sweep_fails(
        self, qt_app, mock_magnet, mock_gate, mock_lockin
    ):
        """
        Verify that Sweep2D enters ERROR state when inner Sweep1D fails.

        This test reproduces the bug where:
        1. Inner sweep fails (try_set returns False, mark_error is called)
        2. mark_done is called (because step_param returns None)
        3. mark_done doesn't check for ERROR state, so it proceeds
        4. State is overwritten from ERROR to DONE
        5. completed signal triggers Sweep2D.update_values
        6. Sweep2D continues to next outer step instead of stopping
        """
        # Create a 2D sweep with fast inner sweep
        # Inner sweep: B from 0 to 8 T (will fail at 8.0 since limit is 7.8)
        # Outer sweep: Vtg from -1 to 1 V (small range to keep test fast)
        sweep2d = Sweep2D(
            [mock_magnet.B, 0.0, 8.0, 1.0],  # Inner: B, step=1T for speed
            [mock_gate.Vtg, -1.0, 1.0, 0.5],  # Outer: Vtg
            inter_delay=0.001,  # Fast inner sweep
            outer_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        sweep2d.follow_param(mock_lockin.x)

        # Track state changes
        states_seen = []
        error_messages = []

        def record_state(update_dict):
            states_seen.append(sweep2d.progressState.state)
            if sweep2d.progressState.error_message:
                error_messages.append(sweep2d.progressState.error_message)

        sweep2d.update_signal.connect(record_state)

        # Start the sweep
        sweep2d.start(ramp_to_start=False)

        # Wait for sweep to complete or error
        timeout = 30  # seconds
        start_time = time.time()
        while sweep2d.progressState.state == SweepState.RUNNING:
            QCoreApplication.processEvents()
            time.sleep(0.01)
            if time.time() - start_time > timeout:
                sweep2d.kill()
                pytest.fail("Sweep timed out")

        # Process remaining events
        for _ in range(10):
            QCoreApplication.processEvents()
            time.sleep(0.01)

        # Verify that sweep ended in ERROR state, not DONE
        assert sweep2d.progressState.state == SweepState.ERROR, (
            f"Expected ERROR state, got {sweep2d.progressState.state}. "
            f"States seen: {states_seen}"
        )

        # Verify error message mentions the inner sweep failure
        assert sweep2d.progressState.error_message is not None
        assert "Inner sweep error" in sweep2d.progressState.error_message or \
               "Failed to set" in sweep2d.progressState.error_message

        # Clean up
        sweep2d.kill()

    def test_mark_done_does_not_overwrite_error_state(
        self, qt_app, mock_magnet, mock_gate, mock_lockin
    ):
        """
        Verify that mark_done does not overwrite ERROR state.

        This is a unit test for the specific bug in mark_done.
        """
        sweep2d = Sweep2D(
            [mock_magnet.B, 0.0, 1.0, 0.1],
            [mock_gate.Vtg, 0.0, 1.0, 0.1],
            inter_delay=0.01,
            outer_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        sweep2d.follow_param(mock_lockin.x)

        # Manually set to ERROR state (simulating what mark_error does)
        sweep2d.progressState.state = SweepState.ERROR
        sweep2d.progressState.error_message = "Test error"

        # Call mark_done (this is what happens when step_param returns None)
        sweep2d.mark_done()

        # Verify state is still ERROR (the fix)
        assert sweep2d.progressState.state == SweepState.ERROR, (
            f"mark_done should not overwrite ERROR state, but state is now {sweep2d.progressState.state}"
        )

        sweep2d.kill()

    def test_update_values_checks_error_state(
        self, qt_app, mock_magnet, mock_gate, mock_lockin
    ):
        """
        Verify that Sweep2D.update_values checks for ERROR state before continuing.
        """
        sweep2d = Sweep2D(
            [mock_magnet.B, 0.0, 1.0, 0.1],
            [mock_gate.Vtg, 0.0, 1.0, 0.1],
            inter_delay=0.01,
            outer_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        sweep2d.follow_param(mock_lockin.x)

        # Record the original outer setpoint
        original_out_setpoint = sweep2d.out_setpoint

        # Manually set to ERROR state
        sweep2d.progressState.state = SweepState.ERROR
        sweep2d.progressState.error_message = "Test error"

        # Also set inner sweep to DONE (simulating completion)
        sweep2d.in_sweep.progressState.state = SweepState.DONE

        # Call update_values (simulating completion callback)
        sweep2d.update_values()

        # Verify outer setpoint was NOT incremented (sweep should not continue)
        assert sweep2d.out_setpoint == original_out_setpoint, (
            f"update_values should not continue when in ERROR state. "
            f"out_setpoint changed from {original_out_setpoint} to {sweep2d.out_setpoint}"
        )

        sweep2d.kill()

    def test_inner_sweep_error_propagates_immediately(
        self, qt_app, mock_magnet, mock_gate, mock_lockin
    ):
        """
        Verify that when inner sweep enters ERROR state,
        Sweep2D also enters ERROR state before update_values can continue.
        """
        sweep2d = Sweep2D(
            [mock_magnet.B, 0.0, 1.0, 0.1],
            [mock_gate.Vtg, 0.0, 1.0, 0.1],
            inter_delay=0.01,
            outer_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        sweep2d.follow_param(mock_lockin.x)

        # Simulate inner sweep error by calling mark_error on inner sweep
        # This should propagate to the outer sweep via the parent reference
        sweep2d.in_sweep.mark_error("Test inner sweep error")

        # Verify that outer sweep is also in ERROR state
        assert sweep2d.progressState.state == SweepState.ERROR, (
            f"Inner sweep error should propagate to outer sweep. "
            f"Outer sweep state: {sweep2d.progressState.state}"
        )

        # Verify error message was propagated
        assert sweep2d.progressState.error_message is not None
        assert "Inner sweep error" in sweep2d.progressState.error_message

        sweep2d.kill()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
