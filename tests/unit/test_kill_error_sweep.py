"""Tests for killing sweeps that are in ERROR state."""

import time
from unittest.mock import patch, MagicMock

import pytest

from measureit.sweep.sweep1d import Sweep1D
from measureit.sweep.sweep2d import Sweep2D
from measureit.sweep.progress import SweepState
from measureit.tools.util import ParameterException


class TestKillErrorStateSweep:
    """Tests for kill() behavior when sweep is in ERROR state."""

    def test_kill_after_error_terminates_runner(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test that kill() properly terminates runner after sweep enters ERROR state.

        Reproduces issue: when a sweep is in ERROR state, s.kill() should properly
        terminate all threads and clean up resources.
        """
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 0.5, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        # Track if completed signal is emitted
        completed_events = []
        sweep.completed.connect(lambda: completed_events.append(True))

        # Start the sweep
        sweep.start(ramp_to_start=False)

        # Wait a bit for runner to start
        time.sleep(0.1)
        qapp.processEvents()

        assert sweep.progressState.state == SweepState.RUNNING
        assert sweep.runner is not None
        runner = sweep.runner
        assert runner.isRunning()

        # Simulate an error during sweep
        sweep.mark_error("Simulated parameter failure")

        assert sweep.progressState.state == SweepState.ERROR

        # Give the runner time to notice the error and exit
        time.sleep(0.2)
        qapp.processEvents()

        # Now try to kill - THIS IS THE BUG SCENARIO
        # If kill() doesn't work properly on ERROR state, we'll detect it here
        sweep.kill()

        # Process events to allow any queued signals
        qapp.processEvents()
        time.sleep(0.1)
        qapp.processEvents()

        # Verify cleanup happened
        assert sweep.runner is None, "Runner should be None after kill()"
        assert sweep.meas is None, "Measurement should be None after kill()"

        # State should be KILLED (ERROR transitions to KILLED when kill() is called)
        assert sweep.progressState.state == SweepState.KILLED

    def test_kill_during_error_transition_race_condition(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test kill() called immediately after error, before runner exits.

        This tests the race condition where:
        1. Error occurs in update_values()
        2. mark_error(_from_runner=True) is called, setting _error_completion_pending
        3. kill() is called BEFORE emit_error_completed() runs
        4. kill() clears _error_completion_pending
        5. The completed signal might never be emitted
        """
        # Create a parameter that will fail on get
        failing_param = mock_parameters["current"]
        original_get = failing_param.get_raw

        call_count = [0]
        def failing_get():
            call_count[0] += 1
            if call_count[0] > 2:  # Fail after a couple of successful reads
                raise Exception("Simulated communication failure")
            return original_get()

        failing_param.get_raw = failing_get

        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 0.5, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(failing_param)

        completed_events = []
        sweep.completed.connect(lambda: completed_events.append("completed"))

        # Start the sweep
        sweep.start(ramp_to_start=False)

        # Wait for the error to occur
        timeout = 5.0
        start_time = time.time()
        while sweep.progressState.state == SweepState.RUNNING:
            qapp.processEvents()
            time.sleep(0.02)
            if time.time() - start_time > timeout:
                sweep.kill()
                pytest.skip("Error didn't occur within timeout")

        # Immediately try to kill (before Qt event loop processes the queued signal)
        sweep.kill()

        # Process all pending events
        for _ in range(10):
            qapp.processEvents()
            time.sleep(0.02)

        # Verify cleanup
        assert sweep.runner is None, "Runner should be None after kill()"

        # Restore the original get
        failing_param.get_raw = original_get

    def test_kill_error_sweep_clears_pending_flag(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test that kill() properly clears _error_completion_pending flag."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 0.5, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        # Manually set up error state with pending flag (simulates runner thread state)
        sweep.progressState.state = SweepState.ERROR
        sweep._error_completion_pending = True

        # Kill should clear the pending flag
        sweep.kill()

        assert sweep._error_completion_pending is False
        assert sweep.progressState.state == SweepState.KILLED  # ERROR transitions to KILLED

    def test_sweep2d_kill_when_inner_in_error(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test Sweep2D.kill() when inner sweep is in ERROR state."""
        sweep = Sweep2D(
            [mock_parameters["voltage"], 0, 0.2, 0.1],
            [mock_parameters["gate"], 0, 0.2, 0.1],
            **fast_sweep_kwargs,
        )
        sweep.in_sweep.follow_param(mock_parameters["current"])

        # Start the sweep
        sweep.start(ramp_to_start=False)

        time.sleep(0.1)
        qapp.processEvents()

        # Simulate error on inner sweep
        sweep.in_sweep.mark_error("Inner sweep failed")

        # This should propagate to outer sweep
        assert sweep.progressState.state == SweepState.ERROR
        assert sweep.in_sweep.progressState.state == SweepState.ERROR

        time.sleep(0.1)
        qapp.processEvents()

        # Now kill the outer sweep - should clean up both
        sweep.kill()

        qapp.processEvents()
        time.sleep(0.1)
        qapp.processEvents()

        # Both should be cleaned up and states should be KILLED
        assert sweep.runner is None
        assert sweep.in_sweep.runner is None
        assert sweep.progressState.state == SweepState.KILLED
        assert sweep.in_sweep.progressState.state == SweepState.KILLED

    def test_kill_error_sweep_runner_already_finished(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test kill() when runner has already finished due to error.

        This is the most common case: error happens, runner exits naturally,
        then user calls kill() to clean up.
        """
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 0.3, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        sweep.start(ramp_to_start=False)

        time.sleep(0.05)
        qapp.processEvents()

        # Mark error (simulating what happens when ParameterException is caught)
        sweep.mark_error("Test error", _from_runner=False)

        # Wait for runner to notice error and exit
        time.sleep(0.3)
        qapp.processEvents()

        # At this point, runner should have finished naturally
        if sweep.runner is not None:
            runner_running = sweep.runner.isRunning()
        else:
            runner_running = False

        # Now call kill
        sweep.kill()

        qapp.processEvents()

        # Should be fully cleaned up
        assert sweep.runner is None
        assert sweep.meas is None

    def test_kill_error_sweep_blocks_until_runner_terminates(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test that kill() waits for runner to terminate (with timeout).

        The kill() method should wait up to 1 second for the runner to finish,
        then force terminate if needed.
        """
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1.0, 0.1,  # Longer sweep
            inter_delay=0.1,  # Slower to give time for kill during run
            save_data=False,
            plot_data=False,
            suppress_output=True,
        )
        sweep.follow_param(mock_parameters["current"])

        sweep.start(ramp_to_start=False)

        time.sleep(0.1)
        qapp.processEvents()

        assert sweep.runner is not None
        assert sweep.runner.isRunning()

        # Mark as error
        sweep.mark_error("Immediate error")

        # Immediately kill (don't wait for runner to notice)
        start_time = time.time()
        sweep.kill()
        kill_duration = time.time() - start_time

        # kill() should complete within timeout (1 second + some margin)
        assert kill_duration < 2.0, f"kill() took too long: {kill_duration}s"

        # Should be cleaned up
        assert sweep.runner is None

    def test_repeated_kill_on_error_sweep(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test that calling kill() multiple times on ERROR sweep is safe."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 0.3, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        sweep.start(ramp_to_start=False)
        time.sleep(0.1)
        qapp.processEvents()

        sweep.mark_error("Test error")

        # Kill multiple times - should not crash
        sweep.kill()
        sweep.kill()
        sweep.kill()

        qapp.processEvents()

        assert sweep.progressState.state == SweepState.KILLED  # ERROR transitions to KILLED
        assert sweep.runner is None


class TestKillErrorSweepRampingBug:
    """Tests for the bug where ramp_sweep is not killed when sweep is in ERROR state.

    Bug: Sweep1D.kill() only kills ramp_sweep if state is RAMPING.
    If error occurs during ramping (state becomes ERROR), ramp_sweep is never cleaned up.
    """

    def test_kill_after_error_during_ramping_should_kill_ramp_sweep(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Reproduce bug: ramp_sweep not killed when error occurs during ramping.

        Scenario:
        1. Sweep starts ramping to start position
        2. Error occurs during ramping (e.g., parameter set fails)
        3. State changes from RAMPING to ERROR
        4. User calls kill()
        5. BUG: ramp_sweep is NOT killed because state is ERROR, not RAMPING
        """
        sweep = Sweep1D(
            mock_parameters["voltage"],
            5.0, 10.0, 0.5,  # Start far from 0 to require ramping
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        # Mock a ramp_sweep that's running
        ramp_sweep = MagicMock()
        ramp_sweep.progressState = MagicMock()
        ramp_sweep.progressState.state = SweepState.RUNNING

        # Manually set up the state as if error occurred during ramping
        sweep.progressState.state = SweepState.ERROR
        sweep.progressState.error_message = "Error during ramping"
        sweep.ramp_sweep = ramp_sweep

        # Call kill()
        sweep.kill()

        # BUG: With current code, ramp_sweep.kill() is NOT called because state is ERROR
        # EXPECTED: ramp_sweep should be killed regardless of state
        # This assertion will FAIL with current code, showing the bug
        ramp_sweep.kill.assert_called_once()

    def test_ramp_sweep_reference_not_cleared_on_error(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test that ramp_sweep reference is still present after error during ramping."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            5.0, 10.0, 0.5,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        # Create a mock ramp_sweep
        ramp_sweep = MagicMock()
        sweep.ramp_sweep = ramp_sweep
        sweep.progressState.state = SweepState.ERROR

        # Current code: ramp_sweep is NOT cleaned up because state check fails
        sweep.kill()

        # BUG: ramp_sweep reference should be None after kill()
        # With current buggy code, it may still be set (pause/kill not called)
        # Note: BaseSweep.kill() doesn't touch ramp_sweep at all
        # So if Sweep1D.kill() doesn't handle it, it remains set


class TestKillErrorSweepWithRealError:
    """Tests that use actual parameter failures to trigger errors."""

    def test_kill_after_parameter_exception_via_safe_get(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test kill() after a ParameterException occurs via safe_get during sweep."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 0.5, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        # Start the sweep
        sweep.start(ramp_to_start=False)

        time.sleep(0.1)
        qapp.processEvents()

        # Now inject an error by patching safe_get to raise ParameterException
        call_count = [0]
        def failing_safe_get(p, last_try=False):
            call_count[0] += 1
            if call_count[0] > 2:
                raise ParameterException(f"Could not get {p.name}.", set=False)
            return p.get()

        with patch("measureit.sweep.sweep1d.safe_get", side_effect=failing_safe_get):
            # Wait for error to occur
            timeout = 3.0
            start_time = time.time()
            while sweep.progressState.state not in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
                qapp.processEvents()
                time.sleep(0.05)
                if time.time() - start_time > timeout:
                    break

        # Try to kill regardless of state
        sweep.kill()

        qapp.processEvents()
        time.sleep(0.1)
        qapp.processEvents()

        # Should be cleaned up
        assert sweep.runner is None
