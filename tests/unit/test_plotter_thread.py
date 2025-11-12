"""Unit tests for Plotter functionality."""

import pytest
from unittest.mock import Mock, MagicMock, patch
import numpy as np

from measureit._internal.plotter_thread import Plotter
from measureit.sweep.sweep1d import Sweep1D


class TestPlotterInit:
    """Test Plotter initialization."""

    def test_init_with_sweep(self, mock_parameters, fast_sweep_kwargs):
        """Test Plotter initializes with a sweep."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        plotter = Plotter(sweep)

        assert plotter.sweep == sweep
        assert plotter.finished is False
        assert plotter.kill_flag is False

    def test_init_creates_qobject(self, mock_parameters, fast_sweep_kwargs):
        """Test that Plotter is a QObject."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        plotter = Plotter(sweep)

        from PyQt5.QtCore import QObject
        assert isinstance(plotter, QObject)


class TestPlotterDataQueue:
    """Test data queue management."""

    def test_has_data_queue(self, mock_parameters, fast_sweep_kwargs):
        """Test that plotter has data queue."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        plotter = Plotter(sweep)

        assert hasattr(plotter, "data_queue")

    def test_add_data_method(self, mock_parameters, fast_sweep_kwargs):
        """Test that add_data method exists."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        plotter = Plotter(sweep)

        assert hasattr(plotter, "add_data")
        assert callable(plotter.add_data)


class TestPlotterRun:
    """Test run method structure."""

    def test_run_method_exists(self, mock_parameters, fast_sweep_kwargs):
        """Test that run method exists."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1,
            **fast_sweep_kwargs,
        )

        plotter = Plotter(sweep)

        assert hasattr(plotter, "run")
        assert callable(plotter.run)


@pytest.mark.integration
class TestPlotterIntegration:
    """Integration tests for Plotter."""

    def test_create_plotter_with_sweep(self, mock_parameters, fast_sweep_kwargs):
        """Test creating plotter with sweep."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 0.1, 0.01,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        plotter = Plotter(sweep)

        assert plotter.sweep == sweep
        assert hasattr(plotter, "data_queue")

    def test_plotter_with_runner(self, mock_parameters, fast_sweep_kwargs):
        """Test plotter working with runner."""
        from measureit._internal.runner_thread import RunnerThread

        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 0.1, 0.01,
            **fast_sweep_kwargs,
        )

        plotter = Plotter(sweep)
        runner = RunnerThread(sweep)

        # Connect plotter to runner
        runner.add_plotter(plotter)

        assert runner.plotter == plotter
        assert plotter.sweep == sweep
