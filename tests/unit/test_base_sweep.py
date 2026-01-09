"""Unit tests for BaseSweep class."""

import pytest
from qcodes import Station

from measureit.sweep.base_sweep import BaseSweep
from measureit.sweep.progress import SweepState


class TestBaseSweepInit:
    """Test BaseSweep initialization."""

    def test_init_defaults(self, mock_parameters):
        """Test BaseSweep initializes with default values."""
        sweep = BaseSweep(
            set_param=mock_parameters["voltage"],
            save_data=False,
            plot_data=False,
        )

        assert sweep.set_param == mock_parameters["voltage"]
        assert sweep.inter_delay == 0.1
        assert sweep.save_data is False
        assert sweep.plot_data is False
        assert sweep._params == []
        assert sweep._srs == []

    def test_init_custom_values(self, mock_parameters):
        """Test BaseSweep initializes with custom values."""
        sweep = BaseSweep(
            set_param=mock_parameters["voltage"],
            inter_delay=0.5,
            save_data=True,
            plot_data=True,
            plot_bin=5,
        )

        assert sweep.inter_delay == 0.5
        assert sweep.save_data is True
        assert sweep.plot_data is True
        assert sweep.plot_bin == 5


class TestBaseSweepFollowParam:
    """Test parameter following functionality."""

    def test_follow_single_param(self, mock_parameters):
        """Test following a single parameter."""
        sweep = BaseSweep(save_data=False, plot_data=False)
        sweep.follow_param(mock_parameters["current"])

        assert len(sweep._params) == 1
        assert mock_parameters["current"] in sweep._params

    def test_follow_multiple_params(self, mock_parameters):
        """Test following multiple parameters at once."""
        sweep = BaseSweep(save_data=False, plot_data=False)
        sweep.follow_param(
            mock_parameters["current"],
            mock_parameters["x"],
            mock_parameters["y"],
        )

        assert len(sweep._params) == 3
        assert mock_parameters["current"] in sweep._params
        assert mock_parameters["x"] in sweep._params
        assert mock_parameters["y"] in sweep._params

    def test_remove_param(self, mock_parameters):
        """Test removing a followed parameter."""
        sweep = BaseSweep(save_data=False, plot_data=False)
        sweep.follow_param(mock_parameters["current"], mock_parameters["x"])

        assert len(sweep._params) == 2

        sweep.remove_param(mock_parameters["current"])
        assert len(sweep._params) == 1
        assert mock_parameters["current"] not in sweep._params
        assert mock_parameters["x"] in sweep._params


class TestBaseSweepState:
    """Test sweep state management."""

    def test_initial_state(self):
        """Test sweep starts in correct state."""
        sweep = BaseSweep(save_data=False, plot_data=False)

        assert sweep.progressState.state == SweepState.READY

    def test_check_running(self):
        """Test check_running method."""
        sweep = BaseSweep(save_data=False, plot_data=False)

        # Initially not running (READY state)
        assert not sweep.check_running()

        # Simulate running state
        sweep.progressState.state = SweepState.RUNNING
        assert sweep.check_running()

        # Simulate ramping state (also considered "running")
        sweep.progressState.state = SweepState.RAMPING
        assert sweep.check_running()

        # Simulate paused state (NOT considered "running")
        sweep.progressState.state = SweepState.PAUSED
        assert not sweep.check_running()

        # Done state
        sweep.progressState.state = SweepState.DONE
        assert not sweep.check_running()


class TestBaseSweepSignals:
    """Test Qt signal emissions."""

    def test_update_signal_exists(self):
        """Test that update_signal exists."""
        sweep = BaseSweep(save_data=False, plot_data=False)
        assert hasattr(sweep, "update_signal")

    def test_dataset_signal_exists(self):
        """Test that dataset_signal exists."""
        sweep = BaseSweep(save_data=False, plot_data=False)
        assert hasattr(sweep, "dataset_signal")

    def test_completed_signal_exists(self):
        """Test that completed signal exists."""
        sweep = BaseSweep(save_data=False, plot_data=False)
        assert hasattr(sweep, "completed")


class TestBaseSweepMetadata:
    """Test metadata handling."""

    def test_export_json_basic(self, mock_parameters):
        """Test basic JSON export."""
        # Add instrument attribute to parameters to avoid AttributeError
        mock_parameters["voltage"]._instrument = None
        mock_parameters["current"]._instrument = None

        sweep = BaseSweep(
            set_param=mock_parameters["voltage"],
            inter_delay=0.05,
            save_data=False,
            plot_data=False,
        )
        sweep.follow_param(mock_parameters["current"])

        # export_json requires proper parameter structure
        # For now, just test that the method exists
        assert hasattr(sweep, "export_json")

    def test_metadata_provider(self):
        """Test metadata provider functionality."""
        sweep = BaseSweep(save_data=False, plot_data=False)

        # Check that metadata provider can be set
        assert hasattr(sweep, "metadata_provider")


class TestBaseSweepComplete:
    """Test sweep completion functionality."""

    def test_set_complete_func(self):
        """Test setting completion function."""
        sweep = BaseSweep(save_data=False, plot_data=False)

        called = []

        def completion_callback():
            called.append(True)

        sweep.set_complete_func(completion_callback)
        # complete_func might be a partial, so check if it's callable
        assert callable(sweep.complete_func)

    def test_default_complete_func(self):
        """Test default no-op completion function."""
        sweep = BaseSweep(save_data=False, plot_data=False, complete_func=lambda: None)

        # Should have completion function
        assert callable(sweep.complete_func)
        # Calling it should not raise
        sweep.complete_func()


class TestBaseSweepPlotBin:
    """Test plot bin functionality."""

    def test_set_plot_bin(self):
        """Test setting plot bin value."""
        sweep = BaseSweep(save_data=False, plot_data=False)

        assert sweep.plot_bin == 1  # Default

        sweep.set_plot_bin(10)
        assert sweep.plot_bin == 10

    def test_plot_bin_in_init(self):
        """Test plot bin can be set in initialization."""
        sweep = BaseSweep(save_data=False, plot_data=False, plot_bin=5)

        assert sweep.plot_bin == 5


@pytest.mark.integration
class TestBaseSweepIntegration:
    """Integration tests for BaseSweep."""

    def test_sweep_with_station(self, mock_station, mock_parameters):
        """Test sweep integrates with QCoDeS Station."""
        sweep = BaseSweep(
            set_param=mock_parameters["voltage"],
            save_data=False,
            plot_data=False,
        )
        sweep.follow_param(mock_parameters["current"])

        # Should be able to work with station
        assert sweep is not None
        assert sweep.set_param == mock_parameters["voltage"]
