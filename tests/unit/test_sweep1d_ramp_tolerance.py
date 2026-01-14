"""Test for ramp tolerance bug in Sweep1D.done_ramping.

This test reproduces the issue where the hardcoded tolerance (step * 1e-4)
in done_ramping() is too tight for small step sizes used in nanometer-scale
scanning (e.g., AFM, NV microscopy).

Bug: The tolerance in done_ramping uses hardcoded 1e-4 instead of self.err,
causing false "Ramping failed" errors with small step sizes.

Example error from bug report:
    Ramping failed (possible that the direction was changed while ramping).
    Expected Scan position x final value: 0.0. Actual value: 4e-08.
    Error: 1.5e-08, Tolerance: 5e-12.

Analysis:
- step = 5e-8 (50nm)
- tolerance = step * 1e-4 = 5e-12 (5 picometers) - TOO TIGHT!
- position_error = |4e-8 - 0| - |5e-8/2| = 1.5e-8 (15nm)
- 1.5e-8 > 5e-12, so error is thrown even though 15nm is reasonable

These tests FAIL when the bug is present and PASS after the fix.
"""

import pytest
from unittest.mock import patch, MagicMock

from measureit.sweep.sweep1d import Sweep1D
from measureit.sweep.progress import SweepState


class TestRampToleranceBug:
    """Tests that FAIL due to the hardcoded tolerance bug in done_ramping.

    These tests demonstrate the expected (correct) behavior. They will:
    - FAIL when the bug is present (current state)
    - PASS after the bug is fixed
    """

    def test_done_ramping_should_not_error_for_reasonable_position(
        self, mock_parameters, fast_sweep_kwargs
    ):
        """Test that done_ramping should NOT mark ERROR for reasonable position errors.

        Bug reproduction from error report:
        - step = 5e-8 (50nm)
        - Expected: 0.0, Actual: 4e-08 (40nm off)
        - position_error = 1.5e-8 (15nm after half-step grace)

        With err=0.5 (50%), tolerance = 25nm, so 15nm error should pass.
        Before fix: hardcoded 1e-4 gave tolerance = 5pm (unrealistic).

        This test FAILS with the bug (tolerance too tight), PASSES after fix.
        """
        step = 5e-8  # 50nm (from bug report)
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=4.5e-7,
            step=step,
            err=0.5,  # 50% tolerance - reasonable for position errors
            **fast_sweep_kwargs,
        )

        # Simulate position slightly off due to floating point accumulation
        expected_value = 0.0
        actual_value = 4e-08  # 40nm off (from bug report)

        with patch('measureit.sweep.sweep1d.safe_get', return_value=actual_value):
            sweep.progressState.state = SweepState.RAMPING
            sweep.ramp_sweep = MagicMock()
            sweep.ramp_sweep.progressState.state = SweepState.DONE

            sweep.done_ramping(expected_value, start_on_finish=False, pd=None)

            # With err=0.5: tolerance = 50nm * 0.5 = 25nm
            # position_error = 15nm < 25nm -> should pass
            # Before fix: tolerance was 5pm, so 15nm would fail
            assert sweep.progressState.state == SweepState.READY, (
                f"Sweep should be READY after ramping, but got {sweep.progressState.state}. "
                f"tolerance={step*sweep.err}, position_error~15nm"
            )

    def test_tolerance_should_use_err_parameter(self, mock_parameters, fast_sweep_kwargs):
        """Test that done_ramping should use the configurable err parameter.

        The err parameter exists and is used elsewhere in Sweep1D, but done_ramping
        uses a hardcoded 1e-4 instead. This inconsistency is the bug.

        With err=0.5 (50%), a 40nm error on 50nm step should be acceptable:
        - tolerance = 50nm * 0.5 = 25nm
        - position_error = 40nm - 25nm (grace) = 15nm
        - 15nm < 25nm tolerance -> should pass

        This test FAILS with the bug.
        """
        step = 5e-8  # 50nm
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=4.5e-7,
            step=step,
            err=0.5,  # 50% tolerance - should allow 25nm error
            **fast_sweep_kwargs,
        )

        expected_value = 0.0
        actual_value = 4e-08  # 40nm off

        with patch('measureit.sweep.sweep1d.safe_get', return_value=actual_value):
            sweep.progressState.state = SweepState.RAMPING
            sweep.ramp_sweep = MagicMock()
            sweep.ramp_sweep.progressState.state = SweepState.DONE

            sweep.done_ramping(expected_value, start_on_finish=False, pd=None)

            # With 50% tolerance, position_error (15nm) < tolerance (25nm)
            # Should be READY, not ERROR
            assert sweep.progressState.state == SweepState.READY, (
                f"With err=0.5, tolerance should be {step*0.5}=25nm, "
                f"but bug uses {step*1e-4}=5pm instead"
            )

    def test_small_position_error_should_pass(self, mock_parameters, fast_sweep_kwargs):
        """Test that small position errors well within half-step should pass.

        Even with the default err=1e-2, a position error much smaller than
        half the step should definitely pass.

        This test FAILS with the bug for very small steps.
        """
        step = 5e-8  # 50nm
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=4.5e-7,
            step=step,
            # default err=1e-2
            **fast_sweep_kwargs,
        )

        expected_value = 0.0
        # Position error of 1nm - should definitely be acceptable
        actual_value = 1e-9  # 1nm off

        with patch('measureit.sweep.sweep1d.safe_get', return_value=actual_value):
            sweep.progressState.state = SweepState.RAMPING
            sweep.ramp_sweep = MagicMock()
            sweep.ramp_sweep.progressState.state = SweepState.DONE

            sweep.done_ramping(expected_value, start_on_finish=False, pd=None)

            # 1nm error is well within half-step (25nm) grace period
            # position_error = 1nm - 25nm = -24nm (negative = within grace)
            # Should definitely be READY
            assert sweep.progressState.state == SweepState.READY, (
                "1nm position error should be acceptable for 50nm step"
            )


class TestRampToleranceVerification:
    """Helper tests to verify the bug mechanics (these should pass regardless)."""

    def test_position_error_formula_matches_bug_report(self):
        """Verify the position_error calculation matches the bug report values."""
        step = 5e-8  # 50nm
        expected = 0.0
        actual = 4e-08  # 40nm

        position_error = abs(actual - expected) - abs(step / 2)

        # |4e-8 - 0| - |5e-8/2| = 4e-8 - 2.5e-8 = 1.5e-8
        assert position_error == pytest.approx(1.5e-8, rel=1e-3)

    def test_buggy_tolerance_value(self):
        """Verify the buggy tolerance calculation produces unrealistic values."""
        step = 5e-8  # 50nm

        # Current buggy calculation in done_ramping line 547
        buggy_tolerance = step * 1e-4  # 5e-12 = 5 picometers

        # What it should be with default err=1e-2
        correct_tolerance = step * 1e-2  # 5e-10 = 0.5 nanometers

        assert buggy_tolerance == pytest.approx(5e-12, rel=1e-3)
        assert correct_tolerance == pytest.approx(5e-10, rel=1e-3)

        # 5 picometers is smaller than atomic radii (~50-300 pm)
        # This is an unrealistic tolerance for any physical instrument
        assert buggy_tolerance < 50e-12, "Buggy tolerance is sub-atomic scale!"

    def test_err_parameter_is_stored(self, mock_parameters, fast_sweep_kwargs):
        """Verify the err parameter is properly stored in sweep."""
        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=1,
            step=0.1,
            err=0.1,
            **fast_sweep_kwargs,
        )

        assert sweep.err == 0.1, "err parameter should be stored"
