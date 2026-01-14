"""Test for bug: sweep stalls when save_data=True but no database is registered.

This test verifies that when save_data=True but no database is registered,
the sweep properly transitions to ERROR state instead of stalling indefinitely.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from measureit.sweep.sweep1d import Sweep1D
from measureit.sweep.progress import SweepState


class TestSaveDataNoDatabaseFix:
    """Test suite verifying the fix for save_data=True without database bug."""

    def test_runner_thread_marks_error_on_database_failure(self, mock_parameters):
        """Test that runner thread marks sweep as ERROR when database init fails.

        This directly tests the fix in runner_thread.py that wraps database
        initialization in try-except and calls mark_error on failure.
        """
        from measureit._internal.runner_thread import RunnerThread

        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=0.5,
            step=0.1,
            inter_delay=0.01,
            save_data=True,
            plot_data=False,
            suppress_output=True,
        )
        sweep.follow_param(mock_parameters["current"])
        sweep._create_measurement()

        # Mock mark_error to track if it's called
        mark_error_called = []
        original_mark_error = sweep.mark_error

        def mock_mark_error(msg, _from_runner=False):
            mark_error_called.append((msg, _from_runner))
            original_mark_error(msg, _from_runner=_from_runner)

        sweep.mark_error = mock_mark_error

        # Mock emit_error_completed to track if it's called
        emit_error_called = []
        original_emit = sweep.emit_error_completed

        def mock_emit():
            emit_error_called.append(True)
            # Don't call original - it uses Qt signals that don't work in fake mode

        sweep.emit_error_completed = mock_emit

        # Mock the measurement's run() to simulate database error
        mock_runner = MagicMock()
        mock_runner.__enter__ = MagicMock(
            side_effect=ValueError("No experiments found. Please create one first.")
        )
        sweep.meas.run = MagicMock(return_value=mock_runner)

        # Create and run the runner thread synchronously (call run() directly)
        runner = RunnerThread(sweep)
        runner.run()  # Run synchronously instead of starting thread

        # Verify mark_error was called with appropriate message
        assert len(mark_error_called) == 1, "Expected mark_error to be called once"
        error_msg, from_runner = mark_error_called[0]
        assert "database" in error_msg.lower() or "experiment" in error_msg.lower(), (
            f"Expected error message about database/experiment, got: {error_msg}"
        )
        assert from_runner is True, "Expected _from_runner=True"

        # Verify emit_error_completed was called
        assert len(emit_error_called) == 1, "Expected emit_error_completed to be called"

        # Verify sweep is in ERROR state
        assert sweep.progressState.state == SweepState.ERROR, (
            f"Expected ERROR state, got {sweep.progressState.state}"
        )

        runner.wait()

    def test_runner_thread_sets_error_message(self, mock_parameters):
        """Test that error message is properly set in progressState."""
        from measureit._internal.runner_thread import RunnerThread

        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=0.5,
            step=0.1,
            inter_delay=0.01,
            save_data=True,
            plot_data=False,
            suppress_output=True,
        )
        sweep.follow_param(mock_parameters["current"])
        sweep._create_measurement()

        # Suppress emit_error_completed since it uses Qt
        sweep.emit_error_completed = MagicMock()

        # Mock database error
        mock_runner = MagicMock()
        mock_runner.__enter__ = MagicMock(
            side_effect=ValueError("No experiments found.")
        )
        sweep.meas.run = MagicMock(return_value=mock_runner)

        runner = RunnerThread(sweep)
        runner.run()

        # Verify error message is set
        assert sweep.progressState.error_message is not None, (
            "Expected error_message to be set"
        )
        assert "database" in sweep.progressState.error_message.lower(), (
            f"Expected 'database' in error message, got: {sweep.progressState.error_message}"
        )

        runner.wait()

    def test_runner_thread_exits_early_on_database_error(self, mock_parameters):
        """Test that runner thread exits early without entering main loop on DB error."""
        from measureit._internal.runner_thread import RunnerThread

        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=0.5,
            step=0.1,
            inter_delay=0.01,
            save_data=True,
            plot_data=False,
            suppress_output=True,
        )
        sweep.follow_param(mock_parameters["current"])
        sweep._create_measurement()

        # Track if update_values is called (it shouldn't be if we exit early)
        update_values_called = []
        original_update = sweep.update_values

        def mock_update():
            update_values_called.append(True)
            return original_update()

        sweep.update_values = mock_update
        sweep.emit_error_completed = MagicMock()

        # Mock database error
        mock_runner = MagicMock()
        mock_runner.__enter__ = MagicMock(
            side_effect=RuntimeError("Database not initialized")
        )
        sweep.meas.run = MagicMock(return_value=mock_runner)

        runner = RunnerThread(sweep)
        runner.run()

        # Verify update_values was NOT called (runner exited early)
        assert len(update_values_called) == 0, (
            "Expected update_values to NOT be called when database init fails"
        )

        runner.wait()

    def test_runner_handles_meas_run_exception(self, mock_parameters):
        """Test that runner handles exception from meas.run() itself."""
        from measureit._internal.runner_thread import RunnerThread

        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=0.5,
            step=0.1,
            inter_delay=0.01,
            save_data=True,
            plot_data=False,
            suppress_output=True,
        )
        sweep.follow_param(mock_parameters["current"])
        sweep._create_measurement()

        sweep.emit_error_completed = MagicMock()

        # Mock meas.run() to raise directly (not __enter__)
        sweep.meas.run = MagicMock(
            side_effect=RuntimeError("Connection to database failed")
        )

        runner = RunnerThread(sweep)
        runner.run()

        # Verify sweep is in ERROR state
        assert sweep.progressState.state == SweepState.ERROR
        assert "database" in sweep.progressState.error_message.lower()

        runner.wait()

    def test_save_data_false_skips_database_init(self, mock_parameters):
        """Test that save_data=False skips database initialization entirely."""
        from measureit._internal.runner_thread import RunnerThread

        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=0.2,
            step=0.1,
            inter_delay=0.01,
            save_data=False,  # No database needed
            plot_data=False,
            suppress_output=True,
        )
        sweep.follow_param(mock_parameters["current"])

        # Don't create measurement - it shouldn't be needed
        # Track if meas.run is called
        sweep.meas = MagicMock()

        # Set sweep to DONE after first iteration to exit loop
        iteration_count = [0]
        original_update = sweep.update_values

        def mock_update():
            iteration_count[0] += 1
            if iteration_count[0] >= 2:
                sweep.progressState.state = SweepState.DONE
            return None

        sweep.update_values = mock_update
        sweep.update_progress = MagicMock()
        sweep.progressState.state = SweepState.RUNNING

        runner = RunnerThread(sweep)
        runner.run()

        # Verify meas.run was NOT called
        sweep.meas.run.assert_not_called()

        runner.wait()


class TestDatabaseErrorMessages:
    """Tests for error message quality when database is not available."""

    def test_error_message_mentions_database(self, mock_parameters):
        """Test that error message clearly mentions database issue."""
        from measureit._internal.runner_thread import RunnerThread

        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=0.5,
            step=0.1,
            inter_delay=0.01,
            save_data=True,
            plot_data=False,
            suppress_output=True,
        )
        sweep.follow_param(mock_parameters["current"])
        sweep._create_measurement()
        sweep.emit_error_completed = MagicMock()

        # Simulate various database-related errors
        test_errors = [
            ValueError("No experiments found."),
            RuntimeError("Database connection failed"),
            Exception("Could not initialize experiment"),
        ]

        for test_error in test_errors:
            # Reset state
            sweep.progressState.state = SweepState.READY
            sweep.progressState.error_message = None

            mock_runner = MagicMock()
            mock_runner.__enter__ = MagicMock(side_effect=test_error)
            sweep.meas.run = MagicMock(return_value=mock_runner)

            runner = RunnerThread(sweep)
            runner.run()

            # Verify error message starts with "Database initialization failed"
            assert sweep.progressState.error_message is not None
            assert sweep.progressState.error_message.startswith(
                "Database initialization failed"
            ), f"Error message should start with 'Database initialization failed', got: {sweep.progressState.error_message}"

            runner.wait()

    def test_original_error_preserved_in_message(self, mock_parameters):
        """Test that the original exception message is preserved."""
        from measureit._internal.runner_thread import RunnerThread

        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=0.5,
            step=0.1,
            inter_delay=0.01,
            save_data=True,
            plot_data=False,
            suppress_output=True,
        )
        sweep.follow_param(mock_parameters["current"])
        sweep._create_measurement()
        sweep.emit_error_completed = MagicMock()

        original_error_msg = "No experiments found. Please create one first."
        mock_runner = MagicMock()
        mock_runner.__enter__ = MagicMock(side_effect=ValueError(original_error_msg))
        sweep.meas.run = MagicMock(return_value=mock_runner)

        runner = RunnerThread(sweep)
        runner.run()

        # Verify original error message is included
        assert original_error_msg in sweep.progressState.error_message, (
            f"Original error '{original_error_msg}' should be in error message, "
            f"got: {sweep.progressState.error_message}"
        )

        runner.wait()
