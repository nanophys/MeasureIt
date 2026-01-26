"""Unit tests for Sweep2D class."""

import pytest

from measureit.sweep.sweep2d import Sweep2D
from measureit.sweep.sweep1d import Sweep1D
from measureit.sweep.progress import SweepState


class TestSweep2DInit:
    """Test Sweep2D initialization."""

    def test_init_basic(self, mock_parameters, fast_sweep_kwargs):
        """Test basic Sweep2D initialization."""
        in_params = [mock_parameters["voltage"], 0, 1, 0.1]
        out_params = [mock_parameters["gate"], -1, 1, 0.2]

        sweep = Sweep2D(
            in_params,
            out_params,
            outer_delay=0.5,
            **fast_sweep_kwargs,
        )

        assert sweep.in_param == mock_parameters["voltage"]
        assert sweep.in_start == 0
        assert sweep.in_stop == 1
        assert sweep.in_step == 0.1
        assert sweep.set_param == mock_parameters["gate"]
        assert sweep.out_start == -1
        assert sweep.out_stop == 1
        assert sweep.out_step == 0.2

    def test_init_creates_inner_sweep(self, mock_parameters, fast_sweep_kwargs):
        """Test that Sweep2D creates an inner Sweep1D."""
        in_params = [mock_parameters["voltage"], 0, 1, 0.1]
        out_params = [mock_parameters["gate"], -1, 1, 0.2]

        sweep = Sweep2D(
            in_params,
            out_params,
            **fast_sweep_kwargs,
        )

        assert hasattr(sweep, "in_sweep")
        assert isinstance(sweep.in_sweep, Sweep1D)
        assert sweep.in_sweep.set_param == mock_parameters["voltage"]
        assert sweep.in_sweep.bidirectional is True

    def test_init_invalid_params_length(self, mock_parameters, fast_sweep_kwargs):
        """Test that invalid param list raises TypeError."""
        in_params = [mock_parameters["voltage"], 0, 1]  # Missing step
        out_params = [mock_parameters["gate"], -1, 1, 0.2]

        with pytest.raises(TypeError, match="must pass list of 4 object"):
            Sweep2D(in_params, out_params, **fast_sweep_kwargs)

    def test_step_direction_correction_inner(self, mock_parameters, fast_sweep_kwargs):
        """Test that inner step direction is corrected."""
        # Downward sweep with positive step - should be corrected to negative
        in_params = [mock_parameters["voltage"], 1, 0, 0.1]
        out_params = [mock_parameters["gate"], 0, 1, 0.1]

        sweep = Sweep2D(in_params, out_params, **fast_sweep_kwargs)

        assert sweep.in_step < 0  # Should be negative for downward sweep

    def test_step_direction_correction_outer(self, mock_parameters, fast_sweep_kwargs):
        """Test that outer step direction is corrected."""
        # Downward outer sweep with positive step
        in_params = [mock_parameters["voltage"], 0, 1, 0.1]
        out_params = [mock_parameters["gate"], 1, -1, 0.2]

        sweep = Sweep2D(in_params, out_params, **fast_sweep_kwargs)

        assert sweep.out_step < 0  # Should be negative for downward sweep

    def test_out_ministeps(self, mock_parameters, fast_sweep_kwargs):
        """Test out_ministeps parameter."""
        in_params = [mock_parameters["voltage"], 0, 1, 0.1]
        out_params = [mock_parameters["gate"], 0, 1, 0.1]

        sweep = Sweep2D(
            in_params,
            out_params,
            out_ministeps=5,
            **fast_sweep_kwargs,
        )

        assert sweep.out_ministeps == 5

    def test_out_ministeps_minimum(self, mock_parameters, fast_sweep_kwargs):
        """Test that out_ministeps has minimum value of 1."""
        in_params = [mock_parameters["voltage"], 0, 1, 0.1]
        out_params = [mock_parameters["gate"], 0, 1, 0.1]

        sweep = Sweep2D(
            in_params,
            out_params,
            out_ministeps=0,
            **fast_sweep_kwargs,
        )

        assert sweep.out_ministeps == 1


class TestSweep2DInnerSweep:
    """Test inner sweep configuration."""

    def test_inner_sweep_follows_outer_param(self, mock_parameters, fast_sweep_kwargs):
        """Test that inner sweep follows outer parameter."""
        in_params = [mock_parameters["voltage"], 0, 1, 0.1]
        out_params = [mock_parameters["gate"], 0, 1, 0.1]

        sweep = Sweep2D(in_params, out_params, **fast_sweep_kwargs)

        # Inner sweep should follow the outer parameter
        assert mock_parameters["gate"] in sweep.in_sweep._params

    def test_inner_sweep_parent_reference(self, mock_parameters, fast_sweep_kwargs):
        """Test that inner sweep has parent reference."""
        in_params = [mock_parameters["voltage"], 0, 1, 0.1]
        out_params = [mock_parameters["gate"], 0, 1, 0.1]

        sweep = Sweep2D(in_params, out_params, **fast_sweep_kwargs)

        assert hasattr(sweep.in_sweep, "parent")
        assert sweep.in_sweep.parent == sweep

    def test_inner_sweep_metadata_provider(self, mock_parameters, fast_sweep_kwargs):
        """Test that inner sweep uses outer sweep's metadata provider."""
        in_params = [mock_parameters["voltage"], 0, 1, 0.1]
        out_params = [mock_parameters["gate"], 0, 1, 0.1]

        sweep = Sweep2D(in_params, out_params, **fast_sweep_kwargs)

        assert sweep.in_sweep.metadata_provider == sweep


class TestSweep2DFollowParam:
    """Test parameter following in Sweep2D."""

    def test_follow_param(self, mock_parameters, fast_sweep_kwargs):
        """Test following a parameter in 2D sweep."""
        in_params = [mock_parameters["voltage"], 0, 1, 0.1]
        out_params = [mock_parameters["gate"], 0, 1, 0.1]

        sweep = Sweep2D(in_params, out_params, **fast_sweep_kwargs)
        sweep.follow_param(mock_parameters["current"])

        # Should be added to inner sweep's params
        assert mock_parameters["current"] in sweep.in_sweep._params

    def test_follow_multiple_params(self, mock_parameters, fast_sweep_kwargs):
        """Test following multiple parameters."""
        in_params = [mock_parameters["voltage"], 0, 1, 0.1]
        out_params = [mock_parameters["gate"], 0, 1, 0.1]

        sweep = Sweep2D(in_params, out_params, **fast_sweep_kwargs)
        sweep.follow_param(
            mock_parameters["current"],
            mock_parameters["x"],
            mock_parameters["y"],
        )

        assert mock_parameters["current"] in sweep.in_sweep._params
        assert mock_parameters["x"] in sweep.in_sweep._params
        assert mock_parameters["y"] in sweep.in_sweep._params


class TestSweep2DState:
    """Test Sweep2D state management."""

    def test_initial_state(self, mock_parameters, fast_sweep_kwargs):
        """Test initial state of 2D sweep."""
        in_params = [mock_parameters["voltage"], 0, 1, 0.1]
        out_params = [mock_parameters["gate"], 0, 1, 0.1]

        sweep = Sweep2D(in_params, out_params, **fast_sweep_kwargs)

        assert sweep.progressState.state == SweepState.READY

    def test_out_setpoint_initial(self, mock_parameters, fast_sweep_kwargs):
        """Test that outer setpoint starts at out_start."""
        in_params = [mock_parameters["voltage"], 0, 1, 0.1]
        out_params = [mock_parameters["gate"], -1, 1, 0.1]

        sweep = Sweep2D(in_params, out_params, **fast_sweep_kwargs)

        assert sweep.out_setpoint == sweep.out_start


class TestSweep2DErrors:
    """Test error tolerance in Sweep2D."""

    def test_error_params(self, mock_parameters, fast_sweep_kwargs):
        """Test error parameter configuration."""
        in_params = [mock_parameters["voltage"], 0, 1, 0.1]
        out_params = [mock_parameters["gate"], 0, 1, 0.1]

        sweep = Sweep2D(
            in_params,
            out_params,
            err=[0.05, 1e-3],
            **fast_sweep_kwargs,
        )

        assert sweep.err == 0.05
        assert sweep.err_in == 1e-3

    def test_default_error_params(self, mock_parameters, fast_sweep_kwargs):
        """Test default error parameters."""
        in_params = [mock_parameters["voltage"], 0, 1, 0.1]
        out_params = [mock_parameters["gate"], 0, 1, 0.1]

        sweep = Sweep2D(in_params, out_params, **fast_sweep_kwargs)

        assert sweep.err == 0.1
        assert sweep.err_in == 1e-2


class TestSweep2DSignals:
    """Test Qt signals in Sweep2D."""

    def test_heatmap_signal_exists(self, mock_parameters, fast_sweep_kwargs):
        """Test that add_heatmap_data signal exists."""
        in_params = [mock_parameters["voltage"], 0, 1, 0.1]
        out_params = [mock_parameters["gate"], 0, 1, 0.1]

        sweep = Sweep2D(in_params, out_params, **fast_sweep_kwargs)

        assert hasattr(sweep, "add_heatmap_data")


class TestSweep2DStringRepresentation:
    """Test string representations."""

    def test_str_repr(self, mock_parameters, fast_sweep_kwargs):
        """Test string representation includes both parameters."""
        in_params = [mock_parameters["voltage"], 0, 1, 0.1]
        out_params = [mock_parameters["gate"], 0, 1, 0.1]

        sweep = Sweep2D(in_params, out_params, **fast_sweep_kwargs)
        # Add parameters to follow so heatmap_ind is valid
        # The outer parameter is auto-added at index 0, so we need at least 2 params
        sweep.follow_param(mock_parameters["current"])

        str_repr = str(sweep)
        # Should mention it's a 2D sweep
        assert "2D" in str_repr or "Sweep2D" in str_repr


@pytest.mark.integration
class TestSweep2DIntegration:
    """Integration tests for Sweep2D."""

    def test_create_complete_2d_sweep(self, mock_parameters, fast_sweep_kwargs):
        """Test creating a complete 2D sweep configuration."""
        in_params = [mock_parameters["voltage"], 0, 0.1, 0.01]
        out_params = [mock_parameters["gate"], -0.1, 0.1, 0.02]

        sweep = Sweep2D(
            in_params,
            out_params,
            outer_delay=0.1,  # Minimum required outer_delay
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        assert sweep is not None
        assert sweep.in_sweep is not None
        assert mock_parameters["current"] in sweep.in_sweep._params

    def test_nested_sweep_structure(self, mock_parameters, fast_sweep_kwargs):
        """Test that 2D sweep properly nests inner sweep."""
        in_params = [mock_parameters["voltage"], 0, 1, 0.1]
        out_params = [mock_parameters["gate"], 0, 1, 0.1]

        sweep = Sweep2D(in_params, out_params, **fast_sweep_kwargs)

        # Inner sweep should have correct configuration
        assert sweep.in_sweep.begin == sweep.in_start
        assert sweep.in_sweep.end == sweep.in_stop
        # Step might be adjusted for direction, check absolute value
        assert abs(sweep.in_sweep.step) == abs(sweep.in_step)
