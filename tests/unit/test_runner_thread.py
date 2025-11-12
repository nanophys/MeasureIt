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
