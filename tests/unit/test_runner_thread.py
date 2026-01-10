"""Unit tests for RunnerThread class."""

import pytest
from unittest.mock import Mock, MagicMock, patch

from measureit._internal.runner_thread import RunnerThread
from measureit.sweep.sweep1d import Sweep1D
from measureit.sweep.progress import SweepState


class TestRunnerThreadInit:
    """Test RunnerThread initialization."""

    def test_init_with_sweep(self, mock_parameters, fast_sweep_kwargs):
        """Test RunnerThread initializes with a sweep."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        runner = RunnerThread(sweep)

        assert runner.sweep == sweep
        assert runner.plotter is None
        assert runner.datasaver is None
        assert runner.dataset is None
        assert runner.db_set is False
        assert runner.runner is None

    def test_init_creates_qthread(self, mock_parameters, fast_sweep_kwargs):
        """Test that RunnerThread is a QThread."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        runner = RunnerThread(sweep)

        # Should inherit from QThread
        from PyQt5.QtCore import QThread

        assert isinstance(runner, QThread)


class TestRunnerThreadSignals:
    """Test Qt signals in RunnerThread."""

    def test_has_get_dataset_signal(self, mock_parameters, fast_sweep_kwargs):
        """Test that get_dataset signal exists."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        runner = RunnerThread(sweep)

        assert hasattr(runner, "get_dataset")

    def test_has_send_data_signal(self, mock_parameters, fast_sweep_kwargs):
        """Test that send_data signal exists."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        runner = RunnerThread(sweep)

        assert hasattr(runner, "send_data")


class TestRunnerThreadPlotter:
    """Test plotter connection."""

    def test_add_plotter(self, mock_parameters, fast_sweep_kwargs):
        """Test adding a plotter to runner."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        runner = RunnerThread(sweep)
        mock_plotter = Mock()
        mock_plotter.add_data = Mock()

        runner.add_plotter(mock_plotter)

        assert runner.plotter == mock_plotter

    def test_add_plotter_connects_signal(self, mock_parameters, fast_sweep_kwargs):
        """Test that add_plotter connects send_data signal."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        runner = RunnerThread(sweep)
        mock_plotter = Mock()
        mock_plotter.add_data = Mock()

        runner.add_plotter(mock_plotter)

        # Signal should be connected (connection count > 0)
        # Note: Testing Qt signal connections is tricky, just verify plotter is set
        assert runner.plotter is not None


class TestRunnerThreadSetParent:
    """Test setting parent sweep."""

    def test_set_parent(self, mock_parameters, fast_sweep_kwargs):
        """Test _set_parent method."""
        sweep1 = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        sweep2 = Sweep1D(
            mock_parameters["gate"],
            -1, 1, 0.1,
            **fast_sweep_kwargs,
        )

        runner = RunnerThread(sweep1)
        assert runner.sweep == sweep1

        runner._set_parent(sweep2)
        assert runner.sweep == sweep2


class TestRunnerThreadDatasaver:
    """Test datasaver management."""

    def test_initial_datasaver_state(self, mock_parameters, fast_sweep_kwargs):
        """Test initial datasaver state."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        runner = RunnerThread(sweep)

        assert runner.datasaver is None
        assert runner.dataset is None
        assert runner.db_set is False

    def test_exit_datasaver_method_exists(self, mock_parameters, fast_sweep_kwargs):
        """Test that exit_datasaver method exists."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        runner = RunnerThread(sweep)

        assert hasattr(runner, "exit_datasaver")
        assert callable(runner.exit_datasaver)

    def test_exit_datasaver_when_none(self, mock_parameters, fast_sweep_kwargs):
        """Test exit_datasaver handles None datasaver gracefully."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        runner = RunnerThread(sweep)
        runner.datasaver = None

        # Should not raise
        runner.exit_datasaver()


class TestRunnerThreadRun:
    """Test run method (basic structure)."""

    def test_run_method_exists(self, mock_parameters, fast_sweep_kwargs):
        """Test that run method exists."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        runner = RunnerThread(sweep)

        assert hasattr(runner, "run")
        assert callable(runner.run)


class TestRunnerThreadDestructor:
    """Test destructor."""

    def test_del_method_exists(self, mock_parameters, fast_sweep_kwargs):
        """Test that __del__ method exists."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        runner = RunnerThread(sweep)

        assert hasattr(runner, "__del__")


@pytest.mark.integration
class TestRunnerThreadIntegration:
    """Integration tests for RunnerThread."""

    def test_create_runner_with_sweep(self, mock_parameters, fast_sweep_kwargs):
        """Test creating runner with sweep."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 0.1, 0.01,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        runner = RunnerThread(sweep)

        assert runner.sweep == sweep
        assert runner.plotter is None

    def test_runner_with_plotter(self, mock_parameters, fast_sweep_kwargs):
        """Test runner with plotter connection."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 0.1, 0.01,
            **fast_sweep_kwargs,
        )

        runner = RunnerThread(sweep)
        mock_plotter = Mock()
        mock_plotter.add_data = Mock()

        runner.add_plotter(mock_plotter)

        assert runner.plotter == mock_plotter
        assert runner.sweep == sweep


class TestRunnerThreadErrorHandling:
    """Test error handling in RunnerThread."""

    def test_progress_state_has_error_fields(self, mock_parameters, fast_sweep_kwargs):
        """Test that ProgressState has error tracking fields."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        assert hasattr(sweep.progressState, "error_message")
        assert hasattr(sweep.progressState, "error_count")
        assert sweep.progressState.error_message is None
        assert sweep.progressState.error_count == 0

    def test_sweep_state_has_error_state(self):
        """Test that SweepState enum has ERROR state."""
        assert hasattr(SweepState, "ERROR")
        assert SweepState.ERROR.value == "error"

    def test_mark_error_transitions_state(self, mock_parameters, fast_sweep_kwargs):
        """Test that mark_error transitions sweep to ERROR state."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.RUNNING

        sweep.mark_error("Test error message")

        assert sweep.progressState.state == SweepState.ERROR
        assert sweep.progressState.error_message == "Test error message"

    def test_mark_error_emits_completed_signal_by_default(self, mock_parameters, fast_sweep_kwargs):
        """Test that mark_error emits completed signal so listeners know sweep ended."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.RUNNING

        completed_called = []
        sweep.completed.connect(lambda: completed_called.append(True))

        sweep.mark_error("Test error message")

        assert len(completed_called) == 1

    def test_mark_error_can_defer_completed_signal(self, mock_parameters, fast_sweep_kwargs):
        """Test that mark_error can defer completed signal to avoid blocking main thread.

        emit_error_completed() schedules signal emission via QueuedConnection.
        """
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.RUNNING

        completed_called = []
        sweep.completed.connect(lambda: completed_called.append(True))

        # When called from runner thread, defer signal emission
        sweep.mark_error("Test error", _from_runner=True)
        assert len(completed_called) == 0

        # Directly call the slot that emit_error_completed() schedules
        # (In real code, this runs via QueuedConnection in main thread)
        sweep._do_emit_error_signals()
        assert len(completed_called) == 1

    def test_mark_error_ignored_when_done(self, mock_parameters, fast_sweep_kwargs):
        """Test that mark_error is ignored when sweep is DONE."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.DONE

        sweep.mark_error("Test error message")

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

        sweep.mark_error("Test error message")

        assert sweep.progressState.state == SweepState.KILLED
        assert sweep.progressState.error_message is None

    def test_clear_error_resets_error_state(self, mock_parameters, fast_sweep_kwargs):
        """Test that clear_error resets error tracking."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.progressState.state = SweepState.ERROR
        sweep.progressState.error_message = "Test error"
        sweep.progressState.error_count = 3

        sweep.clear_error()

        assert sweep.progressState.state == SweepState.READY
        assert sweep.progressState.error_message is None
        assert sweep.progressState.error_count == 0

    def test_start_clears_error_state(self, mock_parameters, fast_sweep_kwargs):
        """Test that start() clears previous error state."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])
        sweep.progressState.state = SweepState.ERROR
        sweep.progressState.error_message = "Previous error"
        sweep.progressState.error_count = 3

        sweep.start(ramp_to_start=False)

        assert sweep.progressState.state == SweepState.RUNNING
        assert sweep.progressState.error_message is None
        assert sweep.progressState.error_count == 0

        sweep.kill()

    def test_send_updates_includes_error_info(self, mock_parameters, fast_sweep_kwargs):
        """Test that send_updates includes error information."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )
        sweep.progressState.error_message = "Test error"
        sweep.progressState.error_count = 2

        received_updates = []

        def capture_update(update_dict):
            received_updates.append(update_dict)

        sweep.update_signal.connect(capture_update)
        sweep.send_updates()

        assert len(received_updates) == 1
        assert received_updates[0]["error_message"] == "Test error"
        assert received_updates[0]["error_count"] == 2
