# test_float_precision_error.py
"""
Test to reproduce floating point precision errors in sweep calculations.

Issue: When sweeping with very small values (e.g., nanometer scale like 1e-8),
floating point arithmetic can produce tiny negative values like -6.28657265540301e-23
instead of exactly 0.0, causing validation errors on parameters with bounds [0, max].

Example from user:
- Parameter validation: 0.0 to 9.9e-07
- Sweep: x_start=0, x_end=9e-7, x_step=1e-8
- Error: Couldn't set x to -6.28657265540301e-23 (should be 0.0)
"""

import os
import time
import pytest
from qcodes.instrument import Instrument

# Skip sweep execution tests in fake Qt mode - they require real Qt threads
FAKE_QT = os.environ.get("MEASUREIT_FAKE_QT", "").lower() in {"1", "true", "yes"}
skip_in_fake_qt = pytest.mark.skipif(
    FAKE_QT,
    reason="Sweep execution tests require real Qt threads"
)
from qcodes.parameters import Parameter
from qcodes.validators import Numbers

from measureit.sweep.sweep1d import Sweep1D
from measureit.sweep.sweep2d import Sweep2D
from measureit.sweep.progress import SweepState


class NanoscaleInstrument(Instrument):
    """Simulates an AFM or similar nanoscale positioning instrument."""

    def __init__(self, name):
        super().__init__(name)

        # Parameters with strict validation (0 to ~1 micron range)
        # This mimics real AFM scanner limits
        self.add_parameter(
            "x",
            unit="m",
            label="Scan position x",
            vals=Numbers(min_value=0.0, max_value=9.9e-7),
            set_cmd=None,
            get_cmd=None,
            initial_value=0.0,
        )
        self.add_parameter(
            "y",
            unit="m",
            label="Scan position y",
            vals=Numbers(min_value=0.0, max_value=9.9e-7),
            set_cmd=None,
            get_cmd=None,
            initial_value=0.0,
        )
        self.add_parameter(
            "signal",
            unit="V",
            label="Signal",
            set_cmd=None,
            get_cmd=None,
            initial_value=0.0,
        )

    def get_idn(self):
        return {"vendor": "Test", "model": "Nanoscale", "serial": "001", "firmware": "1.0"}


@pytest.fixture
def nanoscale_instrument():
    """Create a nanoscale positioning instrument for testing."""
    name = f"nano_instr_{id(object())}"
    instr = NanoscaleInstrument(name)
    yield instr
    try:
        instr.close()
    except Exception:
        pass


@skip_in_fake_qt
class TestFloatPrecisionInSweep1D:
    """Test floating point precision issues in Sweep1D."""

    def test_sweep1d_nanoscale_no_negative_values(self, qapp, nanoscale_instrument):
        """
        Test that Sweep1D doesn't produce negative values when sweeping from 0.

        This reproduces the bug where floating point errors cause values like
        -6.28657265540301e-23 instead of 0.0.
        """
        x_param = nanoscale_instrument.x

        # Typical nanoscale sweep parameters (like AFM)
        x_start = 0.0
        x_end = 9.0e-7    # 900 nm
        x_step = 1e-8     # 10 nm steps

        sweep = Sweep1D(
            x_param,
            x_start,
            x_end,
            x_step,
            inter_delay=0.001,
            save_data=False,
            plot_data=False,
            bidirectional=True,  # This triggers the return sweep where the issue occurs
        )
        sweep.follow_param(nanoscale_instrument.signal)

        # Start the sweep
        sweep.start(ramp_to_start=True)

        # Wait for sweep to run or error
        timeout = 30
        start_time = time.monotonic()
        while time.monotonic() - start_time < timeout:
            qapp.processEvents()
            if sweep.progressState.state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
                break
            time.sleep(0.1)

        print(f"Final state: {sweep.progressState.state}")
        print(f"Error message: {sweep.progressState.error_message}")

        # The sweep should complete without error
        # If there's a float precision bug, it will try to set negative values
        if sweep.progressState.state == SweepState.ERROR:
            error_msg = sweep.progressState.error_message or ""
            # Check if this is the float precision bug
            if "invalid" in error_msg.lower() and "-" in error_msg:
                pytest.fail(
                    f"Float precision bug detected! Sweep tried to set a negative value: {error_msg}"
                )

        sweep.kill()

    def test_sweep1d_ramp_to_zero_precision(self, qapp, nanoscale_instrument):
        """
        Test that ramping to zero doesn't produce tiny negative values.
        """
        x_param = nanoscale_instrument.x

        # Start at a non-zero value and ramp to start=0
        x_param.set(5e-7)  # Start at 500nm

        sweep = Sweep1D(
            x_param,
            0.0,           # Start at 0
            9.0e-7,        # End at 900nm
            1e-8,          # 10nm steps
            inter_delay=0.001,
            save_data=False,
            plot_data=False,
        )
        sweep.follow_param(nanoscale_instrument.signal)

        # This will ramp from 500nm down to 0 before starting
        sweep.start(ramp_to_start=True)

        timeout = 30
        start_time = time.monotonic()
        while time.monotonic() - start_time < timeout:
            qapp.processEvents()
            if sweep.progressState.state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
                break
            time.sleep(0.1)

        print(f"Final state: {sweep.progressState.state}")
        print(f"Error message: {sweep.progressState.error_message}")

        if sweep.progressState.state == SweepState.ERROR:
            error_msg = sweep.progressState.error_message or ""
            # Check specifically for negative value being set (float precision bug signature)
            # Look for patterns like "-6.28657265540301e-23" which indicates tiny negative float error
            # Exclude normal scientific notation in error messages like "1e-12" for tolerance
            import re
            # Match negative numbers in scientific notation that are tiny (exponent < -15)
            tiny_negative_pattern = r'-\d+\.?\d*e-(?:1[5-9]|[2-9]\d)'
            if re.search(tiny_negative_pattern, error_msg):
                pytest.fail(
                    f"Float precision bug in ramp_to! Tried to set negative value: {error_msg}"
                )
            # Also check for "invalid" combined with a negative sign at the start of a number
            if "invalid" in error_msg.lower() and re.search(r'to\s+-\d', error_msg):
                pytest.fail(
                    f"Float precision bug in ramp_to! Tried to set negative value: {error_msg}"
                )

        sweep.kill()


@skip_in_fake_qt
class TestFloatPrecisionInSweep2D:
    """Test floating point precision issues in Sweep2D."""

    def test_sweep2d_nanoscale_afm_scan(self, qapp, nanoscale_instrument):
        """
        Reproduce the exact user scenario: AFM-style 2D scan with nanoscale parameters.

        User code that failed:
        - x: 0 to 9e-7, step 3e-8
        - y: 0 to 9e-7, step 3e-8
        - err: [0.1, 0.1]
        - Issue: Sweep gets stuck in RUNNING state without error
        """
        x_param = nanoscale_instrument.x
        y_param = nanoscale_instrument.y

        # Parameters from user's failing code
        x_start = 0.0
        x_end = 9.0e-7   # 900 nm
        x_step = 3e-8    # 30 nm steps

        y_start = 0.0
        y_end = 9.0e-7   # 900 nm
        y_step = 3e-8    # 30 nm steps

        sweep = Sweep2D(
            [x_param, x_start, x_end, x_step],
            [y_param, y_start, y_end, y_step],
            inter_delay=0.001,
            outer_delay=0.01,
            save_data=False,
            plot_data=False,
            err=[0.1, 0.1],  # This is the problematic tolerance
        )
        sweep.follow_param(nanoscale_instrument.signal)

        # Start sweep
        sweep.start(ramp_to_start=True)

        # Wait for sweep to run or error
        timeout = 30
        start_time = time.monotonic()
        last_setpoint = None
        stuck_count = 0

        while time.monotonic() - start_time < timeout:
            qapp.processEvents()
            if sweep.progressState.state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
                break

            # Check if sweep is stuck (setpoint not changing)
            current_setpoint = (sweep.out_setpoint, sweep.in_sweep.setpoint)
            if current_setpoint == last_setpoint:
                stuck_count += 1
                if stuck_count > 20:  # Stuck for 2+ seconds
                    print(f"Sweep appears stuck at out={sweep.out_setpoint}, in={sweep.in_sweep.setpoint}")
                    break
            else:
                stuck_count = 0
            last_setpoint = current_setpoint

            time.sleep(0.1)

        print(f"Final state: {sweep.progressState.state}")
        print(f"Error message: {sweep.progressState.error_message}")
        print(f"Out setpoint: {sweep.out_setpoint}")
        print(f"In setpoint: {sweep.in_sweep.setpoint}")

        # Check for stuck condition
        if sweep.progressState.state == SweepState.RUNNING:
            pytest.fail(
                f"Sweep stuck in RUNNING state! out_setpoint={sweep.out_setpoint}, "
                f"in_setpoint={sweep.in_sweep.setpoint}"
            )

        if sweep.progressState.state == SweepState.ERROR:
            error_msg = sweep.progressState.error_message or ""
            # Check for the specific float precision bug signature
            if any(x in error_msg.lower() for x in ["invalid", "must be between"]):
                if "-" in error_msg and "e-" in error_msg:
                    pytest.fail(
                        f"Float precision bug in Sweep2D! Error: {error_msg}"
                    )

        sweep.kill()


class TestFloatArithmeticPrecision:
    """Direct tests of floating point arithmetic that causes the issue."""

    @pytest.mark.xfail(reason="Demonstrates raw Python float precision issue - fixed by _snap_to_step")
    def test_step_accumulation_precision(self):
        """
        Demonstrate the floating point precision issue in step calculations.

        When adding small steps repeatedly, floating point errors accumulate.
        This test intentionally uses raw arithmetic without snapping to show
        the underlying issue that _snap_to_step fixes.
        """
        start = 0.0
        step = 1e-8
        end = 9e-7

        # Simulate stepping forward then backward (bidirectional sweep)
        setpoint = start
        steps_forward = 0
        while setpoint < end:
            setpoint += step
            steps_forward += 1

        print(f"After {steps_forward} steps forward: setpoint = {setpoint}")

        # Now step backward to zero
        steps_backward = 0
        while setpoint > start:
            setpoint -= step
            steps_backward += 1

        print(f"After {steps_backward} steps backward: setpoint = {setpoint}")
        print(f"Expected: 0.0, Got: {setpoint}")
        print(f"Difference from zero: {setpoint - 0.0}")

        # This will likely NOT be exactly zero due to float precision
        # The bug is when this tiny negative value gets sent to an instrument
        # with validation that requires >= 0

        if setpoint < 0:
            print(f"BUG: Setpoint went negative: {setpoint}")
            # This is the root cause of the user's issue
            assert setpoint >= 0, f"Float precision caused negative value: {setpoint}"

    def test_proposed_fix_round_to_step(self):
        """
        Test a proposed fix: round setpoint to step precision.
        """
        start = 0.0
        step = 1e-8
        end = 9e-7

        def round_to_step(value, step_size):
            """Round value to the precision of step_size."""
            if step_size == 0:
                return value
            return round(value / step_size) * step_size

        setpoint = start
        steps_forward = 0
        while setpoint < end:
            setpoint += step
            setpoint = round_to_step(setpoint, step)
            steps_forward += 1

        # Step backward
        steps_backward = 0
        while setpoint > start:
            setpoint -= step
            setpoint = round_to_step(setpoint, step)
            steps_backward += 1

        print(f"With rounding fix - Final setpoint: {setpoint}")

        # With rounding, should be exactly 0.0
        assert setpoint == 0.0, f"Even with rounding, got: {setpoint}"
        assert setpoint >= 0, f"Setpoint should not be negative: {setpoint}"


class TestSnapToStepHelper:
    """Test the _snap_to_step helper function that fixes float precision errors."""

    def test_snap_to_step_basic(self):
        """Test basic snapping with origin=0."""
        from measureit.sweep.base_sweep import BaseSweep

        # The erroneous value from the original bug
        error_value = -6.28657265540301e-23
        origin = 0.0
        step = 1e-8

        result = BaseSweep._snap_to_step(error_value, origin, step)
        assert result == 0.0, f"Expected 0.0, got {result}"

    def test_snap_to_step_forward_backward(self):
        """Test that forward + backward sweep returns to origin."""
        from measureit.sweep.base_sweep import BaseSweep

        origin = 0.0
        step = 1e-8
        end = 9e-7

        setpoint = origin
        # Forward
        while setpoint < end:
            setpoint += step
            setpoint = BaseSweep._snap_to_step(setpoint, origin, step)

        # Backward
        while setpoint > origin:
            setpoint -= step
            setpoint = BaseSweep._snap_to_step(setpoint, origin, step)

        assert setpoint == 0.0, f"Expected 0.0, got {setpoint}"
        assert setpoint >= 0, f"Setpoint should not be negative: {setpoint}"

    def test_snap_to_step_arbitrary_origin(self):
        """Test snapping with non-zero origin (e.g., 1.0001333)."""
        from measureit.sweep.base_sweep import BaseSweep

        origin = 1.0001333
        step = 0.0001
        end = 1.0005333

        setpoint = origin
        # Forward
        while setpoint < end:
            setpoint += step
            setpoint = BaseSweep._snap_to_step(setpoint, origin, step)

        # Backward
        while setpoint > origin:
            setpoint -= step
            setpoint = BaseSweep._snap_to_step(setpoint, origin, step)

        assert setpoint == origin, f"Expected {origin}, got {setpoint}"

    def test_snap_to_step_non_power_of_10(self):
        """Test snapping with non-power-of-10 step (e.g., 2.5e-8)."""
        from measureit.sweep.base_sweep import BaseSweep

        origin = 0.0
        step = 2.5e-8

        # Value that's slightly off due to float error
        value = 7.5e-8 + 1e-20  # Should snap to 7.5e-8 (3 steps)

        result = BaseSweep._snap_to_step(value, origin, step)
        assert result == 7.5e-8, f"Expected 7.5e-8, got {result}"

    def test_snap_to_step_binary_rounding_error(self):
        """Test snapping with step that is not exactly representable in binary floats."""
        from measureit.sweep.base_sweep import BaseSweep

        origin = 0.0
        step = 3e-8

        # 3 * 3e-8 produces 8.999...e-8 in binary floating point
        value = step * 3

        result = BaseSweep._snap_to_step(value, origin, step)
        assert result == 9e-8, f"Expected 9e-8, got {result}"

    def test_snap_to_step_negative_values(self):
        """Test snapping with negative values."""
        from measureit.sweep.base_sweep import BaseSweep

        origin = -1.0
        step = 0.1

        # Simulate sweep from -1.0 to 0.0 and back
        setpoint = origin
        while setpoint < 0.0:
            setpoint += step
            setpoint = BaseSweep._snap_to_step(setpoint, origin, step)

        assert setpoint == 0.0, f"Expected 0.0, got {setpoint}"

        while setpoint > origin:
            setpoint -= step
            setpoint = BaseSweep._snap_to_step(setpoint, origin, step)

        assert setpoint == origin, f"Expected {origin}, got {setpoint}"

    def test_snap_to_step_zero_step(self):
        """Test that step=0 returns value unchanged."""
        from measureit.sweep.base_sweep import BaseSweep

        value = 1.23456
        result = BaseSweep._snap_to_step(value, 0.0, 0)
        assert result == value, f"Expected {value}, got {result}"

    def test_snap_to_step_upper_bound(self):
        """Test that values near upper bound don't overshoot."""
        from measureit.sweep.base_sweep import BaseSweep

        origin = 0.0
        step = 1e-8
        max_valid = 9.9e-7

        # Simulate reaching near the end
        setpoint = 9e-7
        setpoint += step  # 9.1e-7
        setpoint = BaseSweep._snap_to_step(setpoint, origin, step)

        assert setpoint <= max_valid, f"Setpoint {setpoint} exceeds max {max_valid}"
        assert setpoint == 9.1e-7, f"Expected 9.1e-7, got {setpoint}"


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)

    print("=" * 60)
    print("Test: Float arithmetic precision issue")
    print("=" * 60)

    # Direct arithmetic test
    start = 0.0
    step = 1e-8
    end = 9e-7

    setpoint = start
    count = 0
    while setpoint < end:
        setpoint += step
        count += 1

    print(f"After {count} forward steps: {setpoint}")

    # Backward
    while setpoint > start:
        setpoint -= step
        count += 1

    print(f"After backward steps: {setpoint}")
    print(f"Is negative? {setpoint < 0}")

    if setpoint < 0:
        print(f"\nBUG REPRODUCED: Final setpoint is {setpoint}")
        print("This negative value will fail validation on parameters with min_value=0")

    print()
    print("=" * 60)
    print("Test: Sweep1D with nanoscale parameters")
    print("=" * 60)

    instr = NanoscaleInstrument("test_nano")

    sweep = Sweep1D(
        instr.x,
        0.0,
        9e-7,
        1e-8,
        inter_delay=0.001,
        save_data=False,
        plot_data=False,
        bidirectional=True,
    )
    sweep.follow_param(instr.signal)

    sweep.start(ramp_to_start=True)

    timeout = 30
    start_time = time.monotonic()
    while time.monotonic() - start_time < timeout:
        app.processEvents()
        if sweep.progressState.state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
            break
        time.sleep(0.1)

    print(f"State: {sweep.progressState.state}")
    if sweep.progressState.error_message:
        print(f"Error: {sweep.progressState.error_message}")
        if "-" in sweep.progressState.error_message:
            print("\nBUG CONFIRMED: Float precision caused negative value in sweep!")

    sweep.kill()
    instr.close()
