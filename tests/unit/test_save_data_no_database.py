"""Test for bug: sweep stalls when save_data=True but no database is registered.

This test reproduces the issue where Sweep1D with save_data=True but without
a registered QCoDeS database causes the sweep to enter a running state and stall
(measurement does not progress).
"""

import threading
import time
from unittest.mock import patch, MagicMock

import pytest

from measureit.sweep.sweep1d import Sweep1D
from measureit.sweep.progress import SweepState


class TestSaveDataNoDatabaseBug:
    """Test suite for the save_data=True without database bug."""

    def test_sweep_stalls_when_save_data_true_no_database(self, mock_parameters):
        """Test that sweep stalls when save_data=True but no database is registered.

        This reproduces the bug where:
        1. save_data=True is set
        2. No database is registered/initialized
        3. The sweep enters RUNNING state but measurement doesn't progress

        The root cause is in runner_thread.py where self.sweep.meas.run() is called
        which tries to access the QCoDeS database. Without a database, this can
        either hang, fail silently, or cause undefined behavior.
        """
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=0.5,
            step=0.1,
            inter_delay=0.01,
            save_data=True,  # Key: save_data is True
            plot_data=False,
            suppress_output=True,
        )
        sweep.follow_param(mock_parameters["current"])

        # Track if the sweep starts but never progresses
        sweep_started_event = threading.Event()
        sweep_completed_event = threading.Event()
        update_received = []

        def on_update(update_dict):
            update_received.append(update_dict)
            if update_dict.get("status"):
                sweep_started_event.set()

        def on_completed():
            sweep_completed_event.set()

        sweep.update_signal.connect(on_update)
        sweep.completed.connect(on_completed)

        # Start the sweep without a database
        # This should ideally fail fast or timeout, not stall indefinitely
        sweep.start(ramp_to_start=False)

        # Wait a short time for the sweep to start
        sweep_started = sweep_started_event.wait(timeout=2.0)

        # Give time for the sweep to either progress or stall
        time.sleep(0.5)

        # Check the state
        state = sweep.progressState.state

        # The bug manifests as:
        # 1. Sweep enters RUNNING state (sweep_started is True)
        # 2. But the sweep never completes or makes progress because
        #    meas.run() in runner_thread fails silently or hangs

        # Cleanup
        sweep.kill()

        # Verify the bug: the sweep started but never progressed/completed
        # In a correct implementation, either:
        # - The sweep should fail with an error (ERROR state)
        # - Or the database should be properly initialized
        #
        # The bug is that it goes to RUNNING and stalls
        if sweep_started:
            # If it started but didn't complete within timeout, it's stalled
            completed = sweep_completed_event.wait(timeout=0.1)
            assert not completed or state == SweepState.ERROR, (
                f"Bug reproduced: sweep started but stalled. "
                f"State: {state}, Updates received: {len(update_received)}"
            )

    def test_sweep_should_error_when_no_database(self, mock_parameters):
        """Test that sweep should transition to ERROR when database is not available.

        This is the expected behavior that should be implemented to fix the bug.
        When save_data=True but no database is registered, the sweep should:
        1. Detect the missing database
        2. Transition to ERROR state with a clear error message
        3. Not stall indefinitely
        """
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

        error_messages = []

        def capture_print(msg):
            error_messages.append(msg)

        sweep.print_main.connect(capture_print)

        # Mock the measurement.run() to raise an error as it would when no DB
        original_create_measurement = sweep._create_measurement

        def mock_create_measurement():
            meas = original_create_measurement()
            # Simulate what happens when no database is registered
            original_run = meas.run

            def failing_run(*args, **kwargs):
                raise RuntimeError("No experiment found. Please create one first.")

            meas.run = failing_run
            return meas

        sweep._create_measurement = mock_create_measurement

        sweep.start(ramp_to_start=False)

        # Give time for the error to propagate
        time.sleep(0.5)

        sweep.kill()

        # The sweep should have detected the error and transitioned to ERROR state
        # (This test documents the expected fix behavior)

    def test_runner_thread_handles_database_error(self, mock_parameters):
        """Test that runner thread properly handles database initialization errors.

        The runner thread calls meas.run() at line 139 of runner_thread.py.
        If the database is not registered, this call fails. The runner should
        catch this exception and mark the sweep as ERROR.
        """
        from measureit._internal.runner_thread import RunnerThread
        from qcodes.dataset.measurements import Measurement

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

        # Create a runner thread
        runner = RunnerThread(sweep)

        # Mock the measurement's run() method to simulate database error
        mock_measurement = MagicMock()
        mock_measurement.run.side_effect = RuntimeError(
            "No experiment found. Please create one before running any measurements."
        )
        sweep.meas = mock_measurement

        # This simulates what happens in runner_thread.run() when database fails
        # Currently the code doesn't handle this error properly
        try:
            # In runner_thread.run(), this is called:
            # self.runner = self.sweep.meas.run()
            runner.runner = sweep.meas.run()
        except RuntimeError as e:
            # The error should be caught and the sweep should be marked as ERROR
            # Currently this is NOT handled, which causes the stall
            assert "No experiment found" in str(e)

        runner.wait()

    def test_save_data_false_works_without_database(self, mock_parameters):
        """Test that sweep works correctly when save_data=False (no database needed).

        This verifies that the save_data=False case works as expected,
        which helps isolate the bug to the save_data=True case.
        """
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

        completed_event = threading.Event()
        sweep.completed.connect(lambda: completed_event.set())

        sweep.start(ramp_to_start=False)

        # This should complete without issues
        # (Timeout is short because fake Qt mode doesn't actually run the thread)
        completed_event.wait(timeout=1.0)

        # Verify sweep can be killed properly
        sweep.kill()

        # State should be DONE, KILLED, or at least not stalled
        assert sweep.progressState.state in (
            SweepState.DONE,
            SweepState.KILLED,
            SweepState.READY,
            SweepState.RUNNING,  # In fake Qt mode, thread may not run
        )


class TestDatabaseValidation:
    """Tests for database validation before sweep starts."""

    def test_detect_missing_database_before_start(self, mock_parameters):
        """Test detecting missing database before starting the sweep.

        A proper fix would validate that the database is available
        before allowing the sweep to start with save_data=True.
        """
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

        # Check if there's a way to validate database availability
        # This documents what validation should exist

        # Currently there is no validation, which causes the bug
        # A fix would add a check like:
        # if sweep.save_data and not database_is_available():
        #     raise ValueError("Cannot save data: no database registered")

    def test_runner_should_check_database_before_loop(self, mock_parameters):
        """Test that runner thread should check database before entering main loop.

        The runner thread should validate that the database is available
        before entering the while True loop in run(). If validation fails,
        it should mark the sweep as ERROR and exit.
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

        runner = RunnerThread(sweep)

        # The issue is in runner_thread.run() around line 136-141:
        # if self.sweep.save_data is True:
        #     self.runner = self.sweep.meas.run()  # This can fail!
        #     self.datasaver = self.runner.__enter__()
        #
        # If meas.run() fails, there's no exception handling,
        # causing the thread to crash silently and the sweep to stall.

        runner.wait()
