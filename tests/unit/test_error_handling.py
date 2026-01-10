"""Unit tests for error state handling in sweeps and queue."""

from unittest.mock import patch, MagicMock

from measureit.sweep.sweep0d import Sweep0D
from measureit.sweep.sweep1d import Sweep1D
from measureit.sweep.sweep2d import Sweep2D
from measureit.sweep.simul_sweep import SimulSweep
from measureit.sweep.progress import SweepState
from measureit.tools.sweep_queue import SweepQueue
from measureit.tools.util import ParameterException


class TestSweep1DErrorHandling:
    """Test error handling in Sweep1D."""

    def test_mark_error_transitions_to_error_state(self, mock_parameters, fast_sweep_kwargs):
        """Test that mark_error transitions sweep to ERROR state."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.RUNNING

        sweep.mark_error("Test error")

        assert sweep.progressState.state == SweepState.ERROR
        assert sweep.progressState.error_message == "Test error"

    def test_mark_error_emits_completed_signal_by_default(self, mock_parameters, fast_sweep_kwargs):
        """Test that mark_error emits completed signal by default."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.RUNNING

        completed_called = []

        def on_completed():
            completed_called.append(True)

        sweep.completed.connect(on_completed)
        sweep.mark_error("Test error")

        assert len(completed_called) == 1

    def test_mark_error_defers_completed_signal(self, mock_parameters, fast_sweep_kwargs):
        """Test that mark_error can defer completed signal.

        When called from runner thread, _from_runner=True to avoid blocking
        the main event loop. The signal emission is scheduled via
        QMetaObject.invokeMethod with QueuedConnection.
        """
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.RUNNING

        completed_called = []
        sweep.completed.connect(lambda: completed_called.append(True))

        # Defer the signal - with _from_runner=True, no signals emitted
        sweep.mark_error("Test error", _from_runner=True)

        # Signal not emitted yet (deferred)
        assert len(completed_called) == 0
        assert sweep.progressState.state == SweepState.ERROR

        # Directly call the slot that emit_error_completed() schedules
        # (In real code, this runs via QueuedConnection in main thread)
        sweep._do_emit_error_signals()
        assert len(completed_called) == 1

    def test_start_clears_error_state(self, mock_parameters, fast_sweep_kwargs):
        """Test that start() clears previous error state."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 0.1, 0.05,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        # Set error state
        sweep.progressState.state = SweepState.ERROR
        sweep.progressState.error_message = "Previous error"
        sweep.progressState.error_count = 3

        # Start should clear error
        sweep.start(ramp_to_start=False)

        assert sweep.progressState.state == SweepState.RUNNING
        assert sweep.progressState.error_message is None
        assert sweep.progressState.error_count == 0

        sweep.kill()

    def test_clear_error_resets_all_error_fields(self, mock_parameters, fast_sweep_kwargs):
        """Test that clear_error resets all error-related fields."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        # Set error state
        sweep.progressState.state = SweepState.ERROR
        sweep.progressState.error_message = "Test error"
        sweep.progressState.error_count = 5

        sweep.clear_error()

        assert sweep.progressState.state == SweepState.READY
        assert sweep.progressState.error_message is None
        assert sweep.progressState.error_count == 0

    def test_mark_error_ignored_when_already_error(self, mock_parameters, fast_sweep_kwargs):
        """Test that mark_error is idempotent when already in ERROR state."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.ERROR
        sweep.progressState.error_message = "First error"

        completed_count = []
        sweep.completed.connect(lambda: completed_count.append(1))

        # Try to mark error again
        sweep.mark_error("Second error")

        # Should not change message or emit signal again
        assert sweep.progressState.error_message == "First error"
        assert len(completed_count) == 0

    def test_mark_error_ignored_when_done(self, mock_parameters, fast_sweep_kwargs):
        """Test that mark_error is ignored when sweep is DONE."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.DONE

        sweep.mark_error("Test error")

        assert sweep.progressState.state == SweepState.DONE
        assert sweep.progressState.error_message is None

    def test_mark_error_ignored_when_killed(self, mock_parameters, fast_sweep_kwargs):
        """Test that mark_error is ignored when sweep is KILLED."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.KILLED

        sweep.mark_error("Test error")

        assert sweep.progressState.state == SweepState.KILLED
        assert sweep.progressState.error_message is None


class TestSweep2DErrorHandling:
    """Test error handling in Sweep2D."""

    def test_sweep2d_mark_error_does_not_block(self, mock_parameters, fast_sweep_kwargs):
        """Test that Sweep2D.mark_error doesn't call kill() to avoid deadlock.

        When mark_error is called from the inner sweep's runner thread, calling
        kill() would try to wait for the thread from within itself, causing deadlock.
        The inner runner thread exits naturally when it sees ERROR state.
        """
        sweep = Sweep2D(
            [mock_parameters["voltage"], 0, 0.1, 0.05],
            [mock_parameters["gate"], 0, 0.1, 0.05],
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.RUNNING
        sweep.in_sweep.progressState.state = SweepState.RUNNING

        # Track if kill was called (it shouldn't be from mark_error)
        inner_kill_called = []
        original_kill = sweep.in_sweep.kill
        def mock_kill():
            inner_kill_called.append(True)
            original_kill()
        sweep.in_sweep.kill = mock_kill

        sweep.mark_error("Test error")

        # kill() should NOT be called from mark_error to avoid deadlock
        assert len(inner_kill_called) == 0
        assert sweep.progressState.state == SweepState.ERROR

    def test_sweep2d_mark_error_sets_error_state(self, mock_parameters, fast_sweep_kwargs):
        """Test that Sweep2D.mark_error sets both outer and emits completed."""
        sweep = Sweep2D(
            [mock_parameters["voltage"], 0, 0.1, 0.05],
            [mock_parameters["gate"], 0, 0.1, 0.05],
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.RUNNING

        completed_called = []
        sweep.completed.connect(lambda: completed_called.append(True))

        sweep.mark_error("Test 2D error")

        assert sweep.progressState.state == SweepState.ERROR
        assert sweep.progressState.error_message == "Test 2D error"
        assert len(completed_called) == 1

    def test_inner_sweep_error_propagates_to_outer(self, mock_parameters, fast_sweep_kwargs):
        """Test that inner sweep error propagates to outer Sweep2D."""
        sweep = Sweep2D(
            [mock_parameters["voltage"], 0, 0.1, 0.05],
            [mock_parameters["gate"], 0, 0.1, 0.05],
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.RUNNING
        sweep.in_sweep.progressState.state = SweepState.RUNNING

        completed_called = []
        sweep.completed.connect(lambda: completed_called.append(True))

        # Simulate inner sweep error - this should propagate to parent
        sweep.in_sweep.mark_error("Inner sweep failed")

        # Inner sweep has parent reference, so error propagates
        assert sweep.progressState.state == SweepState.ERROR
        assert "Inner sweep error" in sweep.progressState.error_message
        assert len(completed_called) == 1

    def test_inner_sweep_parent_reference(self, mock_parameters, fast_sweep_kwargs):
        """Test that inner sweep has correct parent reference."""
        sweep = Sweep2D(
            [mock_parameters["voltage"], 0, 0.1, 0.05],
            [mock_parameters["gate"], 0, 0.1, 0.05],
            **fast_sweep_kwargs,
        )

        assert sweep.in_sweep.parent is sweep


class TestSweepQueueErrorHandling:
    """Test error handling in SweepQueue."""

    def test_queue_detects_sweep_error_state(self, mock_parameters, fast_sweep_kwargs):
        """Test that SweepQueue detects when a sweep ends in ERROR state."""
        queue = SweepQueue(inter_delay=0.01)

        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 0.1, 0.05,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        # Manually set up the queue state as if a sweep just finished with error
        queue.current_action = sweep
        queue.current_sweep = sweep
        sweep.progressState.state = SweepState.ERROR
        sweep.progressState.error_message = "Test error from sweep"

        # Call begin_next - it should detect the error
        queue.begin_next()

        # Sweep should be killed and queue stopped
        assert queue.current_sweep is None

    def test_queue_logs_error_message(self, mock_parameters, fast_sweep_kwargs):
        """Test that SweepQueue logs the error message."""
        queue = SweepQueue(inter_delay=0.01)

        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 0.1, 0.05,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        queue.current_action = sweep
        queue.current_sweep = sweep
        sweep.progressState.state = SweepState.ERROR
        sweep.progressState.error_message = "Validation failed: value out of range"

        # Mock the logger to capture error logs
        with patch.object(queue.log, 'error') as mock_error:
            queue.begin_next()

            # Check that error was logged
            assert mock_error.call_count >= 1
            # First call should contain the error message
            call_args = str(mock_error.call_args_list)
            assert "Validation failed" in call_args or "error" in call_args.lower()

    def test_queue_stops_on_error(self, mock_parameters, fast_sweep_kwargs):
        """Test that SweepQueue stops processing when a sweep errors."""
        queue = SweepQueue(inter_delay=0.01)

        sweep1 = Sweep1D(
            mock_parameters["voltage"],
            0, 0.1, 0.05,
            **fast_sweep_kwargs,
        )
        sweep1.follow_param(mock_parameters["current"])

        sweep2 = Sweep1D(
            mock_parameters["gate"],
            0, 0.1, 0.05,
            **fast_sweep_kwargs,
        )
        sweep2.follow_param(mock_parameters["current"])

        # Add second sweep to queue (first will be current_action)
        queue.queue.append(sweep2)

        queue.current_action = sweep1
        queue.current_sweep = sweep1
        sweep1.progressState.state = SweepState.ERROR
        sweep1.progressState.error_message = "Sweep1 failed"

        # Call begin_next
        queue.begin_next()

        # Queue should have stopped - sweep2 should still be in queue
        assert len(queue.queue) == 1
        assert queue.current_sweep is None

    def test_queue_continues_normally_on_success(self, mock_parameters, fast_sweep_kwargs):
        """Test that SweepQueue continues normally when sweep completes successfully."""
        queue = SweepQueue(inter_delay=0.01)

        sweep1 = Sweep1D(
            mock_parameters["voltage"],
            0, 0.1, 0.05,
            **fast_sweep_kwargs,
        )
        sweep1.follow_param(mock_parameters["current"])

        sweep2 = Sweep1D(
            mock_parameters["gate"],
            0, 0.1, 0.05,
            **fast_sweep_kwargs,
        )
        sweep2.follow_param(mock_parameters["current"])

        # Add sweep2 to queue
        queue.queue.append(sweep2)

        queue.current_action = sweep1
        queue.current_sweep = sweep1
        sweep1.progressState.state = SweepState.DONE  # Completed successfully

        # begin_next should process sweep2
        # (It will start sweep2, but we don't need to run it fully)
        queue.begin_next()

        # sweep2 should now be current_sweep (started)
        assert queue.current_sweep is sweep2

        # Cleanup
        sweep2.kill()

    def test_queue_state_returns_error_state(self, mock_parameters, fast_sweep_kwargs):
        """Test that queue.state() returns ERROR when current sweep is in error."""
        queue = SweepQueue(inter_delay=0.01)

        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 0.1, 0.05,
            **fast_sweep_kwargs,
        )

        queue.current_sweep = sweep
        sweep.progressState.state = SweepState.ERROR

        assert queue.state() == SweepState.ERROR


class TestErrorStateIntegration:
    """Integration tests for error state handling across components."""

    def test_error_info_in_send_updates(self, mock_parameters, fast_sweep_kwargs):
        """Test that error info is included in update signals."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        sweep.progressState.state = SweepState.ERROR
        sweep.progressState.error_message = "Test error message"
        sweep.progressState.error_count = 1

        updates = []
        sweep.update_signal.connect(lambda d: updates.append(d))

        sweep.send_updates()

        assert len(updates) == 1
        assert updates[0]["state"] == "error"
        assert updates[0]["error_message"] == "Test error message"
        assert updates[0]["error_count"] == 1

    def test_progress_state_preserves_error_on_update(self, mock_parameters, fast_sweep_kwargs):
        """Test that update_progress preserves error information."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        sweep.progressState.error_message = "Preserved error"
        sweep.progressState.error_count = 1

        sweep.update_progress()

        assert sweep.progressState.error_message == "Preserved error"
        assert sweep.progressState.error_count == 1

    def test_sweep2d_error_sets_outer_state(self, mock_parameters, fast_sweep_kwargs):
        """Test that Sweep2D error sets outer sweep to ERROR state.

        Note: Inner sweep is NOT killed from mark_error to avoid deadlock.
        The inner runner thread exits naturally when it sees ERROR state.
        """
        sweep = Sweep2D(
            [mock_parameters["voltage"], 0, 0.1, 0.05],
            [mock_parameters["gate"], 0, 0.1, 0.05],
            **fast_sweep_kwargs,
        )

        sweep.progressState.state = SweepState.RUNNING
        sweep.in_sweep.progressState.state = SweepState.RUNNING

        sweep.mark_error("Cleanup test error")

        # Outer sweep should be in ERROR state
        assert sweep.progressState.state == SweepState.ERROR
        # Inner sweep state is unchanged - it will exit naturally when its runner sees ERROR
        # The inner runner breaks when parent state is ERROR


class TestRunnerThreadErrorSimulation:
    """Tests that simulate the runner thread error handling logic."""

    def test_parameter_exception_immediately_triggers_error(self, mock_parameters, fast_sweep_kwargs):
        """Test that ParameterException immediately triggers error state.

        This simulates the runner_thread behavior: when safe_set fails and raises
        ParameterException (after already retrying once internally), the sweep
        should immediately transition to ERROR state - not continue to the next setpoint.
        """
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.RUNNING

        # Simulate what runner_thread does on ParameterException:
        # Immediately call mark_error (no retry counting at runner level)
        error_message = "Parameter operation failed: value out of range"
        sweep.mark_error(error_message)

        # Sweep should be in ERROR state
        assert sweep.progressState.state == SweepState.ERROR
        assert sweep.progressState.error_message == error_message

    def test_error_stops_sweep_from_continuing(self, mock_parameters, fast_sweep_kwargs):
        """Test that error state prevents sweep from continuing to next setpoint.

        This is the critical behavior: when ParameterException occurs, the sweep
        must NOT continue to the next setpoint - it must stop immediately.
        """
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.RUNNING

        # Simulate error occurring
        sweep.mark_error("Test error")

        # After error, state should be ERROR (not RUNNING)
        assert sweep.progressState.state == SweepState.ERROR

        # The runner loop checks state before calling update_values()
        # So with ERROR state, update_values() should NOT be called
        state = sweep.progressState.state
        assert state != SweepState.RUNNING  # This would prevent update_values() call


class TestRampingFailureErrorHandling:
    """Tests for ramping failure error handling in Sweep1D and SimulSweep."""

    def test_sweep1d_done_ramping_error_on_position_mismatch(self, mock_parameters, fast_sweep_kwargs):
        """Test that Sweep1D.done_ramping() marks error when position doesn't match."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.RAMPING

        completed_called = []
        sweep.completed.connect(lambda: completed_called.append(True))

        # Mock safe_get to return a value far from expected
        with patch("measureit.sweep.sweep1d.safe_get", return_value=0.5):
            # Call done_ramping with expected value 0.0 (far from 0.5)
            sweep.done_ramping(0.0, start_on_finish=False, pd=None)

        # Should be in ERROR state due to position mismatch
        assert sweep.progressState.state == SweepState.ERROR
        assert "Ramping failed" in sweep.progressState.error_message
        assert "tolerance" in sweep.progressState.error_message.lower()
        assert len(completed_called) == 1

    def test_sweep1d_done_ramping_success_when_position_matches(self, mock_parameters, fast_sweep_kwargs):
        """Test that Sweep1D.done_ramping() succeeds when position matches."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.RAMPING

        # Mock safe_get to return a value close to expected
        with patch("measureit.sweep.sweep1d.safe_get", return_value=1.0):
            with patch("measureit.sweep.base_sweep.safe_set"):
                sweep.done_ramping(1.0, start_on_finish=False, pd=None)

        # Should NOT be in ERROR state - position matched
        assert sweep.progressState.state != SweepState.ERROR
        assert sweep.progressState.state == SweepState.READY

    def test_simul_sweep_done_ramping_error_on_position_mismatch(self, mock_parameters, fast_sweep_kwargs):
        """Test that SimulSweep.done_ramping() marks error when position doesn't match."""
        # SimulSweep requires dictionary format
        params_dict = {
            mock_parameters["voltage"]: {"start": 0, "stop": 1, "step": 0.1},
            mock_parameters["gate"]: {"start": 0, "stop": 1, "step": 0.1},
        }
        sweep = SimulSweep(params_dict, **fast_sweep_kwargs)
        sweep.progressState.state = SweepState.RAMPING

        completed_called = []
        sweep.completed.connect(lambda: completed_called.append(True))

        # vals_dict maps parameters to expected final values
        vals_dict = {
            mock_parameters["voltage"]: 0.0,
            mock_parameters["gate"]: 0.0,
        }

        # Mock safe_get to return values far from expected (0.5 instead of 0.0)
        with patch("measureit.sweep.simul_sweep.safe_get", return_value=0.5):
            sweep.done_ramping(vals_dict, start_on_finish=False, pd=None)

        # Should be in ERROR state due to position mismatch
        assert sweep.progressState.state == SweepState.ERROR
        assert "Ramping failed" in sweep.progressState.error_message
        assert len(completed_called) == 1


class TestRampSweepErrorPropagation:
    """Tests for ramp sweep error propagation to parent sweep."""

    def test_sweep1d_ramp_sweep_error_propagates_to_parent(self, mock_parameters, fast_sweep_kwargs):
        """Test that Sweep1D propagates errors from its ramp_sweep."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 5, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.RAMPING

        # Create a mock ramp_sweep that's in ERROR state
        ramp_sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        ramp_sweep.progressState.state = SweepState.ERROR
        ramp_sweep.progressState.error_message = "Parameter set failed during ramp"
        sweep.ramp_sweep = ramp_sweep

        completed_called = []
        sweep.completed.connect(lambda: completed_called.append(True))

        # Call done_ramping - should detect ramp_sweep error and propagate
        sweep.done_ramping(value=0.0, start_on_finish=False, pd=None)

        # Parent should be in ERROR state
        assert sweep.progressState.state == SweepState.ERROR
        assert "Ramp to start failed" in sweep.progressState.error_message
        assert "Parameter set failed during ramp" in sweep.progressState.error_message
        assert len(completed_called) == 1
        # ramp_sweep should be cleaned up
        assert sweep.ramp_sweep is None

    def test_simul_sweep_ramp_sweep_error_propagates_to_parent(self, mock_parameters, fast_sweep_kwargs):
        """Test that SimulSweep propagates errors from its ramp_sweep."""
        params_dict = {
            mock_parameters["voltage"]: {"start": 0, "stop": 5, "step": 0.1},
            mock_parameters["gate"]: {"start": 0, "stop": 5, "step": 0.1},
        }
        sweep = SimulSweep(params_dict, **fast_sweep_kwargs)
        sweep.progressState.state = SweepState.RAMPING

        # Create a mock ramp_sweep that's in ERROR state
        ramp_params = {
            mock_parameters["voltage"]: {"start": 0, "stop": 1, "step": 0.1},
        }
        ramp_sweep = SimulSweep(ramp_params, **fast_sweep_kwargs)
        ramp_sweep.progressState.state = SweepState.ERROR
        ramp_sweep.progressState.error_message = "Communication error during ramp"
        sweep.ramp_sweep = ramp_sweep

        completed_called = []
        sweep.completed.connect(lambda: completed_called.append(True))

        vals_dict = {
            mock_parameters["voltage"]: 0.0,
            mock_parameters["gate"]: 0.0,
        }

        # Call done_ramping - should detect ramp_sweep error and propagate
        sweep.done_ramping(vals_dict, start_on_finish=False, pd=None)

        # Parent should be in ERROR state
        assert sweep.progressState.state == SweepState.ERROR
        assert "Ramp to start failed" in sweep.progressState.error_message
        assert "Communication error during ramp" in sweep.progressState.error_message
        assert len(completed_called) == 1
        # ramp_sweep should be cleaned up
        assert sweep.ramp_sweep is None


class TestSweep2DOuterParamErrorHandling:
    """Tests for Sweep2D outer parameter set error handling."""

    def test_sweep2d_outer_param_set_failure_marks_error(self, mock_parameters, fast_sweep_kwargs):
        """Test that Sweep2D marks error when outer parameter set fails."""
        sweep = Sweep2D(
            [mock_parameters["voltage"], 0, 0.2, 0.1],
            [mock_parameters["gate"], 0, 0.2, 0.1],
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.RUNNING
        sweep.in_sweep.progressState.state = SweepState.DONE
        sweep.out_setpoint = 0.0

        completed_called = []
        sweep.completed.connect(lambda: completed_called.append(True))

        # Mock safe_set to raise an exception
        with patch("measureit.sweep.base_sweep.safe_set", side_effect=ParameterException("Value out of range")):
            # Call update_values which tries to set outer parameter
            sweep.update_values()

        # Should be in ERROR state
        assert sweep.progressState.state == SweepState.ERROR
        assert "Failed to set" in sweep.progressState.error_message
        assert len(completed_called) == 1


class TestSweep0DSafeGetUsage:
    """Tests for Sweep0D safe_get usage."""

    def test_sweep0d_uses_safe_get_in_update_values(self, mock_parameters, fast_sweep_kwargs):
        """Test that Sweep0D.update_values() uses safe_get for parameter reads."""
        sweep = Sweep0D(max_time=10.0, **fast_sweep_kwargs)
        sweep.follow_param(mock_parameters["current"])
        sweep.progressState.state = SweepState.RUNNING
        sweep.progressState.time_elapsed = 0.0

        # Verify safe_get is called for the parameter
        with patch("measureit.sweep.sweep0d.safe_get", return_value=1.23) as mock_safe_get:
            data = sweep.update_values()

        # safe_get should have been called for the followed parameter
        mock_safe_get.assert_called()
        # Data should contain the parameter value
        assert data is not None
        assert any(d[0] == mock_parameters["current"] and d[1] == 1.23 for d in data)


class TestM4GErrorHandling:
    """Tests for M4G magnet error handling with retry limits."""

    def test_m4g_retries_on_read_error(self, mock_parameters, fast_sweep_kwargs):
        """Test that M4G retries on read error before giving up."""
        # Create a mock M4G parameter
        mock_m4g_param = MagicMock()
        mock_m4g_param.name = "field"
        mock_m4g_param.label = "field"
        mock_m4g_param.unit = "T"
        mock_m4g_param.full_name = "m4g_field"

        # Create an M4G mock instrument
        from measureit.Drivers.M4G import M4G
        mock_instrument = MagicMock()
        mock_instrument.field = MagicMock(return_value=0.1)
        mock_m4g_param.instrument = mock_instrument

        # Patch isinstance to recognize our mock as M4G
        with patch("measureit.sweep.sweep1d.isinstance") as mock_isinstance:
            def isinstance_side_effect(obj, cls):
                if cls is M4G:
                    return obj is mock_instrument
                return type.__instancecheck__(cls, obj)
            mock_isinstance.side_effect = isinstance_side_effect

            sweep = Sweep1D(
                mock_m4g_param,
                0, 1, 0.1,
                **fast_sweep_kwargs,
            )
            sweep.progressState.state = SweepState.RUNNING
            sweep.magnet_initialized = True
            sweep.instrument = mock_instrument

            # Mock safe_get to fail multiple times
            call_count = [0]
            def failing_safe_get(param):
                call_count[0] += 1
                raise Exception("Communication error")

            with patch("measureit.sweep.sweep1d.safe_get", side_effect=failing_safe_get):
                result = sweep.step_M4G()

        # Should have retried MAX_M4G_RETRIES times (100) + 1 initial = 101 total
        assert call_count[0] == 101
        assert sweep.progressState.state == SweepState.ERROR
        assert "M4G field read failed" in sweep.progressState.error_message
        assert result is None

    def test_m4g_succeeds_after_retry(self, mock_parameters, fast_sweep_kwargs):
        """Test that M4G succeeds if retry works."""
        # Create a mock M4G parameter
        mock_m4g_param = MagicMock()
        mock_m4g_param.name = "field"
        mock_m4g_param.label = "field"
        mock_m4g_param.unit = "T"
        mock_m4g_param.full_name = "m4g_field"

        # Create an M4G mock instrument
        from measureit.Drivers.M4G import M4G
        mock_instrument = MagicMock()
        mock_instrument.field = MagicMock(return_value=0.1)
        mock_m4g_param.instrument = mock_instrument

        with patch("measureit.sweep.sweep1d.isinstance") as mock_isinstance:
            def isinstance_side_effect(obj, cls):
                if cls is M4G:
                    return obj is mock_instrument
                return type.__instancecheck__(cls, obj)
            mock_isinstance.side_effect = isinstance_side_effect

            sweep = Sweep1D(
                mock_m4g_param,
                0, 1, 0.1,
                **fast_sweep_kwargs,
            )
            sweep.progressState.state = SweepState.RUNNING
            sweep.magnet_initialized = True
            sweep.instrument = mock_instrument

            # Mock safe_get to fail first time, succeed second time
            call_count = [0]
            def sometimes_failing_safe_get(param):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise Exception("Temporary error")
                return 0.05

            with patch("measureit.sweep.sweep1d.safe_get", side_effect=sometimes_failing_safe_get):
                result = sweep.step_M4G()

        # Should have succeeded after retry
        assert call_count[0] == 2
        assert sweep.progressState.state == SweepState.RUNNING  # Not ERROR
        assert result is not None
