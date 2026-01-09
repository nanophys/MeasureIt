"""Unit tests for Sweep0D class."""

import pytest

from measureit.sweep.sweep0d import Sweep0D
from measureit.sweep.progress import SweepState


class TestSweep0DInit:
    """Test Sweep0D initialization."""

    def test_init_defaults(self, fast_sweep_kwargs):
        """Test Sweep0D initializes with defaults."""
        sweep = Sweep0D(**fast_sweep_kwargs)

        assert sweep.set_param is None
        assert sweep.max_time == 1e6
        assert sweep.progressState.state == SweepState.READY

    def test_init_custom_max_time(self, fast_sweep_kwargs):
        """Test Sweep0D with custom max_time."""
        sweep = Sweep0D(max_time=100, **fast_sweep_kwargs)

        assert sweep.max_time == 100

    def test_init_no_set_param(self, fast_sweep_kwargs):
        """Test that Sweep0D has no set parameter."""
        sweep = Sweep0D(**fast_sweep_kwargs)

        assert sweep.set_param is None

    def test_initial_progress(self, fast_sweep_kwargs):
        """Test initial progress is 0."""
        sweep = Sweep0D(**fast_sweep_kwargs)

        assert sweep.progressState.progress == 0.0


class TestSweep0DFollowParam:
    """Test parameter following in Sweep0D."""

    def test_follow_single_param(self, mock_parameters, fast_sweep_kwargs):
        """Test following a single parameter."""
        sweep = Sweep0D(**fast_sweep_kwargs)
        sweep.follow_param(mock_parameters["current"])

        assert len(sweep._params) == 1
        assert mock_parameters["current"] in sweep._params

    def test_follow_multiple_params(self, mock_parameters, fast_sweep_kwargs):
        """Test following multiple parameters."""
        sweep = Sweep0D(**fast_sweep_kwargs)
        sweep.follow_param(
            mock_parameters["current"],
            mock_parameters["voltage"],
            mock_parameters["temperature"],
        )

        assert len(sweep._params) == 3
        assert mock_parameters["current"] in sweep._params
        assert mock_parameters["voltage"] in sweep._params
        assert mock_parameters["temperature"] in sweep._params


class TestSweep0DFlipDirection:
    """Test direction flipping (should not work)."""

    def test_flip_direction_does_not_error(self, fast_sweep_kwargs):
        """Test that flip_direction doesn't raise an error."""
        sweep = Sweep0D(**fast_sweep_kwargs)

        # Should not raise, but also doesn't do anything
        sweep.flip_direction()

    def test_flip_direction_method_exists(self, fast_sweep_kwargs):
        """Test that flip_direction method exists."""
        sweep = Sweep0D(**fast_sweep_kwargs)

        assert hasattr(sweep, "flip_direction")
        assert callable(sweep.flip_direction)


class TestSweep0DStringRepresentation:
    """Test string representations."""

    def test_str_with_max_time(self, fast_sweep_kwargs):
        """Test string representation with max_time."""
        sweep = Sweep0D(max_time=100, **fast_sweep_kwargs)

        str_repr = str(sweep)
        assert "0D Sweep" in str_repr
        assert "100" in str_repr

    def test_str_continuous(self, fast_sweep_kwargs):
        """Test string representation for continuous sweep."""
        # Use a very large max_time instead of None (which may not be supported)
        sweep = Sweep0D(max_time=1e10, **fast_sweep_kwargs)

        str_repr = str(sweep)
        assert "0D" in str_repr or "Sweep" in str_repr

    def test_repr(self, fast_sweep_kwargs):
        """Test repr representation."""
        sweep = Sweep0D(max_time=100, **fast_sweep_kwargs)

        repr_str = repr(sweep)
        assert "Sweep0D" in repr_str
        assert "100" in repr_str


class TestSweep0DState:
    """Test Sweep0D state management."""

    def test_initial_state(self, fast_sweep_kwargs):
        """Test initial state is READY."""
        sweep = Sweep0D(**fast_sweep_kwargs)

        assert sweep.progressState.state == SweepState.READY

    def test_check_running(self, fast_sweep_kwargs):
        """Test check_running method."""
        sweep = Sweep0D(**fast_sweep_kwargs)

        # Initially not running
        assert not sweep.check_running()

        # Simulate running state
        sweep.progressState.state = SweepState.RUNNING
        assert sweep.check_running()


class TestSweep0DEstimateTime:
    """Test time estimation."""

    def test_estimate_time_ready_state(self, fast_sweep_kwargs):
        """Test estimate_time when in READY state."""
        sweep = Sweep0D(max_time=100, **fast_sweep_kwargs)

        estimate = sweep.estimate_time(verbose=False)
        assert estimate == 100

    def test_estimate_time_done_state(self, fast_sweep_kwargs):
        """Test estimate_time when in DONE state."""
        sweep = Sweep0D(max_time=100, **fast_sweep_kwargs)
        sweep.progressState.state = SweepState.DONE

        estimate = sweep.estimate_time(verbose=False)
        assert estimate == 0

    def test_estimate_time_method_exists(self, fast_sweep_kwargs):
        """Test that estimate_time method exists."""
        sweep = Sweep0D(**fast_sweep_kwargs)

        assert hasattr(sweep, "estimate_time")
        assert callable(sweep.estimate_time)


class TestSweep0DMetadata:
    """Test metadata and JSON export."""

    def test_export_json_specific_method(self, fast_sweep_kwargs):
        """Test that _export_json_specific method exists."""
        sweep = Sweep0D(max_time=100, **fast_sweep_kwargs)

        assert hasattr(sweep, "_export_json_specific")
        assert callable(sweep._export_json_specific)

    def test_export_json_specific_includes_max_time(self, fast_sweep_kwargs):
        """Test that JSON export includes max_time."""
        sweep = Sweep0D(max_time=100, **fast_sweep_kwargs)

        json_dict = {"attributes": {}}
        result = sweep._export_json_specific(json_dict)

        assert "max_time" in result["attributes"]
        assert result["attributes"]["max_time"] == 100

    def test_export_json_specific_set_param_none(self, fast_sweep_kwargs):
        """Test that JSON export sets set_param to None."""
        sweep = Sweep0D(max_time=100, **fast_sweep_kwargs)

        json_dict = {"attributes": {}}
        result = sweep._export_json_specific(json_dict)

        assert result["set_param"] is None

    def test_from_json_class_method(self, fast_sweep_kwargs):
        """Test that from_json class method exists."""
        assert hasattr(Sweep0D, "from_json")
        assert callable(Sweep0D.from_json)


class TestSweep0DUpdateValues:
    """Test update_values method."""

    def test_update_values_method_exists(self, fast_sweep_kwargs):
        """Test that update_values method exists."""
        sweep = Sweep0D(**fast_sweep_kwargs)

        assert hasattr(sweep, "update_values")
        assert callable(sweep.update_values)


class TestSweep0DSignals:
    """Test Qt signals."""

    def test_has_print_main_signal(self, fast_sweep_kwargs):
        """Test that print_main signal exists."""
        sweep = Sweep0D(**fast_sweep_kwargs)

        assert hasattr(sweep, "print_main")

    def test_has_completed_signal(self, fast_sweep_kwargs):
        """Test that completed signal exists."""
        sweep = Sweep0D(**fast_sweep_kwargs)

        assert hasattr(sweep, "completed")


@pytest.mark.integration
class TestSweep0DIntegration:
    """Integration tests for Sweep0D."""

    def test_create_simple_time_sweep(self, mock_parameters, fast_sweep_kwargs):
        """Test creating a simple time-based sweep."""
        sweep = Sweep0D(max_time=10, **fast_sweep_kwargs)
        sweep.follow_param(
            mock_parameters["current"],
            mock_parameters["voltage"],
        )

        assert sweep.max_time == 10
        assert len(sweep._params) == 2

    def test_create_continuous_sweep(self, mock_parameters, fast_sweep_kwargs):
        """Test creating a continuous sweep (no max_time limit)."""
        sweep = Sweep0D(max_time=1e10, **fast_sweep_kwargs)
        sweep.follow_param(mock_parameters["temperature"])

        assert sweep.max_time == 1e10
        assert mock_parameters["temperature"] in sweep._params

    def test_sweep_with_multiple_readouts(self, mock_parameters, fast_sweep_kwargs):
        """Test 0D sweep with multiple readout parameters."""
        sweep = Sweep0D(max_time=100, **fast_sweep_kwargs)
        sweep.follow_param(
            mock_parameters["current"],
            mock_parameters["voltage"],
            mock_parameters["x"],
            mock_parameters["y"],
        )

        assert len(sweep._params) == 4
