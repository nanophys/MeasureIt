"""Unit tests for Sweep1D class."""

import pytest

from measureit.sweep.sweep1d import Sweep1D


class TestSweep1DInit:
    """Test Sweep1D initialization."""

    def test_init_with_step(self, mock_parameters, fast_sweep_kwargs):
        """Test Sweep1D initialization with step parameter."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=1,
            step=0.1,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        assert sweep.set_param == mock_parameters["voltage"]
        assert sweep.begin == 0
        assert sweep.end == 1
        assert sweep.step == 0.1
        assert sweep.inter_delay == 0.01
        assert mock_parameters["current"] in sweep._params

    def test_init_bidirectional(self, mock_parameters, fast_sweep_kwargs):
        """Test Sweep1D with bidirectional sweep."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=1,
            step=0.1,
            bidirectional=True,
            **fast_sweep_kwargs,
        )

        assert sweep.bidirectional is True

    def test_init_stores_start_stop_as_begin_end(self, mock_parameters, fast_sweep_kwargs):
        """Test that start/stop parameters are stored as begin/end internally."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=1,
            step=0.1,
            **fast_sweep_kwargs,
        )

        # Constructor takes start/stop, but stores as begin/end
        assert hasattr(sweep, "begin")
        assert hasattr(sweep, "end")
        assert sweep.begin == 0
        assert sweep.end == 1


class TestSweep1DStepCalculation:
    """Test step/interval calculation logic."""

    def test_step_direction_positive(self, mock_parameters, fast_sweep_kwargs):
        """Test step is positive when sweeping upward."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=1,
            step=0.1,
            **fast_sweep_kwargs,
        )

        # Step should be positive for upward sweep
        assert sweep.step > 0

    def test_step_direction_negative(self, mock_parameters, fast_sweep_kwargs):
        """Test step is negative when sweeping downward."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=1,
            stop=0,
            step=0.1,  # Given as positive, should be made negative
            **fast_sweep_kwargs,
        )

        # Step should be negative for downward sweep
        assert sweep.step < 0


class TestSweep1DContinuous:
    """Test continuous sweep mode."""

    def test_continuous_mode(self, mock_parameters, fast_sweep_kwargs):
        """Test continuous sweep initialization."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=1,
            step=0.1,
            continual=True,  # Note: parameter is 'continual' not 'continuous'
            **fast_sweep_kwargs,
        )

        assert sweep.continuous is True  # Stored as 'continuous'

    def test_non_continuous_mode(self, mock_parameters, fast_sweep_kwargs):
        """Test non-continuous sweep (default)."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=1,
            step=0.1,
            **fast_sweep_kwargs,
        )

        assert sweep.continuous is False


class TestSweep1DMetadata:
    """Test Sweep1D metadata and JSON export."""

    def test_export_json_basic(self, mock_parameters, fast_sweep_kwargs):
        """Test basic JSON export structure."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=1,
            step=0.1,
            **fast_sweep_kwargs,
        )

        # Just test that export_json method exists
        assert hasattr(sweep, "export_json")
        assert callable(sweep.export_json)

    def test_str_repr(self, mock_parameters, fast_sweep_kwargs):
        """Test string representations."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=1,
            step=0.1,
            **fast_sweep_kwargs,
        )

        str_repr = str(sweep)
        assert "1D Sweep" in str_repr
        assert mock_parameters["voltage"].label in str_repr

        repr_str = repr(sweep)
        assert "Sweep1D" in repr_str


class TestSweep1DRampTo:
    """Test ramp functionality."""

    def test_has_ramp_to_method(self, mock_parameters, fast_sweep_kwargs):
        """Test that sweep has ramp_to method."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=1,
            step=0.1,
            **fast_sweep_kwargs,
        )

        assert hasattr(sweep, "ramp_to")
        assert callable(sweep.ramp_to)


class TestSweep1DFollowParams:
    """Test parameter following in Sweep1D."""

    def test_follow_multiple_params(self, mock_parameters, fast_sweep_kwargs):
        """Test following multiple parameters."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=1,
            step=0.1,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(
            mock_parameters["current"],
            mock_parameters["x"],
            mock_parameters["y"],
        )

        assert len(sweep._params) == 3
        assert mock_parameters["current"] in sweep._params
        assert mock_parameters["x"] in sweep._params
        assert mock_parameters["y"] in sweep._params


class TestSweep1DBackMultiplier:
    """Test backward sweep multiplier."""

    def test_back_multiplier(self, mock_parameters, fast_sweep_kwargs):
        """Test back_multiplier parameter."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=1,
            step=0.1,
            back_multiplier=0.5,
            **fast_sweep_kwargs,
        )

        assert sweep.back_multiplier == 0.5


@pytest.mark.integration
class TestSweep1DIntegration:
    """Integration tests for Sweep1D."""

    def test_create_simple_sweep(self, mock_parameters, fast_sweep_kwargs):
        """Test creating a simple sweep with fast parameters."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=0.1,
            step=0.01,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        assert sweep is not None
        assert sweep.begin == 0
        assert sweep.end == 0.1
        assert sweep.step == 0.01

    def test_sweep_with_multiple_readouts(self, mock_parameters, fast_sweep_kwargs):
        """Test sweep with multiple readout parameters."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=0.1,
            step=0.01,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(
            mock_parameters["current"],
            mock_parameters["x"],
            mock_parameters["y"],
        )

        assert len(sweep._params) == 3
