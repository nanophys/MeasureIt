"""Tests for sweep parameter validation."""

import warnings

import numpy as np
import pytest
from qcodes.parameters import Parameter
from qcodes.validators import Enum, Numbers

from measureit.sweep.base_sweep import BaseSweep
from measureit.sweep.simul_sweep import SimulSweep
from measureit.sweep.sweep1d import Sweep1D
from measureit.sweep.sweep2d import Sweep2D


@pytest.fixture
def param_with_bounds():
    """Create a parameter with validation bounds [-10, 10]."""
    return Parameter(
        name="voltage",
        label="Voltage",
        unit="V",
        vals=Numbers(-10, 10),
        set_cmd=None,
        get_cmd=lambda: 0,
    )


@pytest.fixture
def param_no_bounds():
    """Create a parameter without validation bounds."""
    return Parameter(
        name="current",
        label="Current",
        unit="A",
        set_cmd=None,
        get_cmd=lambda: 0,
    )


@pytest.fixture
def param_with_enum():
    """Create a parameter with Enum validator (discrete values only)."""
    return Parameter(
        name="temperature_K",
        label="Temperature",
        unit="K",
        vals=Enum(0.02, 2.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0),
        set_cmd=None,
        get_cmd=lambda: 0.02,
    )


class TestGetValidatorBounds:
    """Tests for _get_validator_bounds helper."""

    def test_returns_bounds_for_numbers_validator(self, param_with_bounds):
        min_val, max_val = BaseSweep._get_validator_bounds(param_with_bounds)
        assert min_val == -10
        assert max_val == 10

    def test_returns_none_for_no_validator(self, param_no_bounds):
        min_val, max_val = BaseSweep._get_validator_bounds(param_no_bounds)
        assert min_val is None
        assert max_val is None

    def test_returns_none_for_infinite_bounds(self):
        param = Parameter(
            name="unbounded",
            vals=Numbers(),  # -inf to +inf by default
            set_cmd=None,
            get_cmd=lambda: 0,
        )
        min_val, max_val = BaseSweep._get_validator_bounds(param)
        assert min_val is None
        assert max_val is None


class TestValidateParamSweepRange:
    """Tests for _validate_param_sweep_range helper."""

    def test_valid_range_passes(self, param_with_bounds):
        # Should not raise
        BaseSweep._validate_param_sweep_range(param_with_bounds, -5, 5)

    def test_start_exceeds_max_raises(self, param_with_bounds):
        with pytest.raises(ValueError, match="start value.*exceeds.*maximum"):
            BaseSweep._validate_param_sweep_range(param_with_bounds, 15, 20)

    def test_stop_exceeds_max_raises(self, param_with_bounds):
        with pytest.raises(ValueError, match="stop value.*exceeds.*maximum"):
            BaseSweep._validate_param_sweep_range(param_with_bounds, 0, 15)

    def test_start_below_min_raises(self, param_with_bounds):
        with pytest.raises(ValueError, match="start value.*below.*minimum"):
            BaseSweep._validate_param_sweep_range(param_with_bounds, -15, 0)

    def test_stop_below_min_raises(self, param_with_bounds):
        with pytest.raises(ValueError, match="stop value.*below.*minimum"):
            BaseSweep._validate_param_sweep_range(param_with_bounds, 0, -15)

    def test_no_bounds_passes_any_range(self, param_no_bounds):
        # Should not raise for any values
        BaseSweep._validate_param_sweep_range(param_no_bounds, -1000, 1000)

    def test_boundary_value_warns(self, param_with_bounds):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            BaseSweep._validate_param_sweep_range(param_with_bounds, -10, 5)
            assert len(w) == 1
            assert "at the minimum validation limit" in str(w[0].message)

    def test_both_boundaries_warn(self, param_with_bounds):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            BaseSweep._validate_param_sweep_range(param_with_bounds, -10, 10)
            assert len(w) == 1
            assert "minimum validation limit" in str(w[0].message)
            assert "maximum validation limit" in str(w[0].message)

    def test_infinite_stop_skips_validation(self, param_with_bounds):
        # Should not raise for infinite stop (used by GateLeakage)
        BaseSweep._validate_param_sweep_range(param_with_bounds, 0, np.inf)

    def test_negative_infinite_start_skips_validation(self, param_with_bounds):
        # Should not raise for negative infinite start
        BaseSweep._validate_param_sweep_range(param_with_bounds, -np.inf, 0)

    def test_enum_validator_raises(self, param_with_enum):
        """Enum validators should be rejected - discrete values cannot be swept linearly."""
        with pytest.raises(ValueError, match="Enum validator.*discrete allowed values"):
            BaseSweep._validate_param_sweep_range(param_with_enum, 0.02, 30)

    def test_enum_validator_error_message_includes_values(self, param_with_enum):
        """Error message should include the allowed discrete values."""
        with pytest.raises(ValueError, match="0.02"):
            BaseSweep._validate_param_sweep_range(param_with_enum, 0.02, 30)


class TestSweep1DValidation:
    """Tests for Sweep1D initialization validation."""

    def test_valid_sweep_creates_successfully(self, param_with_bounds):
        s = Sweep1D(
            param_with_bounds,
            -5,
            5,
            0.1,
            inter_delay=0.1,
            plot_data=False,
            save_data=False,
        )
        assert s.begin == -5
        assert s.end == 5
        s.kill()

    def test_invalid_sweep_raises_valueerror(self, param_with_bounds):
        with pytest.raises(ValueError, match="exceeds.*maximum"):
            Sweep1D(
                param_with_bounds,
                0,
                15,
                0.1,
                inter_delay=0.1,
                plot_data=False,
                save_data=False,
            )

    def test_sweep_without_bounds_succeeds(self, param_no_bounds):
        s = Sweep1D(
            param_no_bounds,
            -100,
            100,
            1,
            inter_delay=0.1,
            plot_data=False,
            save_data=False,
        )
        s.kill()

    def test_enum_param_raises_valueerror(self, param_with_enum):
        """Sweep1D should reject parameters with Enum validators at creation time."""
        with pytest.raises(ValueError, match="Enum validator.*discrete allowed values"):
            Sweep1D(
                param_with_enum,
                0.02,
                30,
                5,
                inter_delay=0.1,
                plot_data=False,
                save_data=False,
            )


class TestSweep2DValidation:
    """Tests for Sweep2D initialization validation."""

    def test_valid_sweep_creates_successfully(self, param_with_bounds, param_no_bounds):
        s = Sweep2D(
            [param_no_bounds, -5, 5, 1],
            [param_with_bounds, -5, 5, 1],
            inter_delay=0.1,
            outer_delay=0.1,
            plot_data=False,
            save_data=False,
        )
        s.kill()

    def test_invalid_outer_param_raises(self, param_with_bounds, param_no_bounds):
        with pytest.raises(ValueError, match="outer.*exceeds.*maximum"):
            Sweep2D(
                [param_no_bounds, -5, 5, 1],
                [param_with_bounds, -5, 15, 1],
                inter_delay=0.1,
                outer_delay=0.1,
                plot_data=False,
                save_data=False,
            )

    def test_invalid_inner_param_raises(self, param_with_bounds, param_no_bounds):
        with pytest.raises(ValueError, match="inner.*exceeds.*maximum"):
            Sweep2D(
                [param_with_bounds, -5, 15, 1],
                [param_no_bounds, -5, 5, 1],
                inter_delay=0.1,
                outer_delay=0.1,
                plot_data=False,
                save_data=False,
            )

    def test_outer_delay_too_small_raises(self, param_no_bounds):
        with pytest.raises(ValueError, match="outer_delay.*too small"):
            Sweep2D(
                [param_no_bounds, -5, 5, 1],
                [param_no_bounds, -5, 5, 1],
                inter_delay=0.1,
                outer_delay=0.05,
                plot_data=False,
                save_data=False,
            )

    def test_outer_delay_none_raises(self, param_no_bounds):
        with pytest.raises(ValueError, match="outer_delay.*too small"):
            Sweep2D(
                [param_no_bounds, -5, 5, 1],
                [param_no_bounds, -5, 5, 1],
                inter_delay=0.1,
                outer_delay=None,
                plot_data=False,
                save_data=False,
            )


class TestSimulSweepValidation:
    """Tests for SimulSweep initialization validation."""

    def test_valid_sweep_creates_successfully(self, param_with_bounds):
        s = SimulSweep(
            {param_with_bounds: {"start": -5, "stop": 5, "step": 1}},
            inter_delay=0.1,
            plot_data=False,
            save_data=False,
        )
        s.kill()

    def test_invalid_param_raises(self, param_with_bounds):
        with pytest.raises(ValueError, match="exceeds.*maximum"):
            SimulSweep(
                {param_with_bounds: {"start": -5, "stop": 15, "step": 1}},
                inter_delay=0.1,
                plot_data=False,
                save_data=False,
            )

    def test_multiple_params_all_validated(self, param_with_bounds, param_no_bounds):
        # First param invalid
        with pytest.raises(ValueError):
            SimulSweep(
                {
                    param_with_bounds: {"start": -15, "stop": 5, "step": 1},
                    param_no_bounds: {"start": -5, "stop": 5, "step": 1},
                },
                inter_delay=0.1,
                plot_data=False,
                save_data=False,
            )


class TestInterDelayValidation:
    """Tests for inter_delay validation (inherited from BaseSweep)."""

    def test_inter_delay_too_small_raises(self, param_no_bounds):
        with pytest.raises(ValueError, match="inter_delay.*too small"):
            Sweep1D(
                param_no_bounds,
                0,
                5,
                0.1,
                inter_delay=0.005,
                plot_data=False,
                save_data=False,
            )

    def test_inter_delay_none_raises(self, param_no_bounds):
        with pytest.raises(ValueError, match="inter_delay.*too small"):
            Sweep1D(
                param_no_bounds,
                0,
                5,
                0.1,
                inter_delay=None,
                plot_data=False,
                save_data=False,
            )


class TestFollowParamSetpointValidation:
    """Tests for setpoint parameter validation in follow_param."""

    def test_basesweep_follow_setpoint_raises(self, param_no_bounds):
        """Test that following the setpoint parameter in BaseSweep raises clear error."""
        sweep = BaseSweep(
            set_param=param_no_bounds,
            save_data=False,
            plot_data=False,
        )

        # Attempting to follow the setpoint should raise ValueError
        with pytest.raises(
            ValueError,
            match=r"Cannot follow setpoint parameter.*automatically recorded as the independent variable",
        ):
            sweep.follow_param(param_no_bounds)

        # The parameter should not be added to the list
        assert param_no_bounds not in sweep._params
        sweep.kill()

    def test_sweep1d_follow_setpoint_raises(self, param_with_bounds, param_no_bounds):
        """Test that following the setpoint parameter in Sweep1D raises clear error."""
        sweep = Sweep1D(
            param_with_bounds,
            -5,
            5,
            0.1,
            inter_delay=0.1,
            plot_data=False,
            save_data=False,
        )

        # Following other parameters should work
        sweep.follow_param(param_no_bounds)
        assert param_no_bounds in sweep._params

        # But following the setpoint should raise
        with pytest.raises(
            ValueError,
            match=r"Cannot follow setpoint parameter.*automatically recorded as the independent variable",
        ):
            sweep.follow_param(param_with_bounds)

        assert param_with_bounds not in sweep._params
        sweep.kill()

    def test_sweep1d_follow_setpoint_in_list_raises(
        self, param_with_bounds, param_no_bounds
    ):
        """Test that following setpoint parameter in a list raises clear error."""
        sweep = Sweep1D(
            param_with_bounds,
            -5,
            5,
            0.1,
            inter_delay=0.1,
            plot_data=False,
            save_data=False,
        )

        # Following the setpoint in a list should also raise
        with pytest.raises(
            ValueError,
            match=r"Cannot follow setpoint parameter.*automatically recorded as the independent variable",
        ):
            sweep.follow_param([param_with_bounds, param_no_bounds])

        sweep.kill()

    def test_sweep2d_follow_inner_setpoint_raises(
        self, param_with_bounds, param_no_bounds
    ):
        """Test that following the inner setpoint parameter in Sweep2D raises clear error."""
        inner_param = param_with_bounds
        outer_param = param_no_bounds
        measure_param = Parameter(
            name="current",
            label="Current",
            unit="A",
            set_cmd=None,
            get_cmd=lambda: 0,
        )

        sweep = Sweep2D(
            [inner_param, -5, 5, 1],
            [outer_param, -5, 5, 1],
            inter_delay=0.1,
            outer_delay=0.1,
            plot_data=False,
            save_data=False,
        )

        # Following measured parameter should work
        sweep.follow_param(measure_param)
        assert measure_param in sweep._params

        # But following inner setpoint should raise
        with pytest.raises(
            ValueError,
            match=r"Cannot follow inner setpoint parameter.*automatically recorded as the independent variable",
        ):
            sweep.follow_param(inner_param)

        sweep.kill()

    def test_sweep2d_follow_outer_setpoint_raises(
        self, param_with_bounds, param_no_bounds
    ):
        """Test that following the outer setpoint parameter in Sweep2D raises clear error."""
        inner_param = param_with_bounds
        outer_param = param_no_bounds
        measure_param = Parameter(
            name="current",
            label="Current",
            unit="A",
            set_cmd=None,
            get_cmd=lambda: 0,
        )

        sweep = Sweep2D(
            [inner_param, -5, 5, 1],
            [outer_param, -5, 5, 1],
            inter_delay=0.1,
            outer_delay=0.1,
            plot_data=False,
            save_data=False,
        )

        # Following measured parameter should work
        sweep.follow_param(measure_param)
        assert measure_param in sweep._params

        # But following outer setpoint should raise
        with pytest.raises(
            ValueError,
            match=r"Cannot follow outer setpoint parameter.*automatically recorded as the independent variable",
        ):
            sweep.follow_param(outer_param)

        sweep.kill()

    def test_sweep2d_follow_both_setpoints_in_list_raises(
        self, param_with_bounds, param_no_bounds
    ):
        """Test that following setpoint parameters in a list raises clear error."""
        inner_param = param_with_bounds
        outer_param = param_no_bounds

        sweep = Sweep2D(
            [inner_param, -5, 5, 1],
            [outer_param, -5, 5, 1],
            inter_delay=0.1,
            outer_delay=0.1,
            plot_data=False,
            save_data=False,
        )

        # Following inner setpoint in a list should raise
        with pytest.raises(ValueError, match=r"Cannot follow inner setpoint parameter"):
            sweep.follow_param([inner_param])

        # Following outer setpoint in a list should raise
        with pytest.raises(ValueError, match=r"Cannot follow outer setpoint parameter"):
            sweep.follow_param([outer_param])

        sweep.kill()
