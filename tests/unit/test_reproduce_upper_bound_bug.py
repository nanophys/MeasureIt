# test_reproduce_upper_bound_bug.py
"""
Reproduce bug: Sweep tries to set value exceeding the endpoint.

Issue: When sweeping from 0.0 to 1.185e-06 with step 3e-8 in bidirectional mode,
the sweep tries to set x to 1.2e-06 which exceeds the max_value of 1.185e-06.

Error message:
    Couldn't set x to 1.2e-06. Trying again. Error: ('1.2e-06 is invalid:
    must be between 0.0 and 1.185e-06 inclusive')

Root Cause Analysis:
===================
The bug is in flip_direction() when bidirectional=True and back_multiplier > 1.

Trace through what happens:
1. Forward sweep ends at setpoint = 1.17e-6 (valid, 39 * 3e-8)
2. flip_direction() is called because bidirectional=True and direction=0:
   - step = 3e-8 * back_multiplier(4) = 1.2e-7, then negated to -1.2e-7
   - setpoint = 1.17e-6 - (-1.2e-7) = 1.29e-6
   - After snap to 1.2e-7 grid: ~1.32e-6
3. Recursive step_param() is called:
   - condition check passes (far from end=0)
   - setpoint = 1.32e-6 + (-1.2e-7) = 1.2e-6
   - try_set(x, 1.2e-6) → FAILS because 1.2e-6 > max_value=1.185e-6

The fundamental issue is that flip_direction() doesn't check if the resulting
setpoint (after the next step) will exceed the original parameter bounds.

Fix Requirements:
1. After flip_direction, ensure the first backward step stays within bounds
2. When the forward sweep end point doesn't align with step grid, the backward
   sweep must start from a valid position that doesn't exceed the end point
"""

import os
import time
import pytest
from qcodes.instrument import Instrument
from qcodes.parameters import Parameter
from qcodes.validators import Numbers

from measureit.sweep.sweep1d import Sweep1D
from measureit.sweep.sweep2d import Sweep2D
from measureit.sweep.base_sweep import BaseSweep
from measureit.sweep.progress import SweepState

# Skip sweep execution tests in fake Qt mode - they require real Qt threads
FAKE_QT = os.environ.get("MEASUREIT_FAKE_QT", "").lower() in {"1", "true", "yes"}
skip_in_fake_qt = pytest.mark.skipif(
    FAKE_QT,
    reason="Sweep execution tests require real Qt threads"
)


class SensorDisplacementDevice(Instrument):
    """Simulates the device from the user's bug report."""

    def __init__(self, name):
        super().__init__(name)

        # Parameters with exact bounds from the bug report
        self.add_parameter(
            "x",
            unit="m",
            label="Scan position x",
            vals=Numbers(min_value=0.0, max_value=1.185e-6),  # Exact max from bug
            set_cmd=None,
            get_cmd=None,
            initial_value=0.0,
        )
        self.add_parameter(
            "y",
            unit="m",
            label="Scan position y",
            vals=Numbers(min_value=0.0, max_value=1.185e-6),  # Exact max from bug
            set_cmd=None,
            get_cmd=None,
            initial_value=0.0,
        )
        self.add_parameter(
            "B1",
            unit="T",
            label="B field 1",
            set_cmd=None,
            get_cmd=None,
            initial_value=0.0,
        )
        self.add_parameter(
            "B2",
            unit="T",
            label="B field 2",
            set_cmd=None,
            get_cmd=None,
            initial_value=0.0,
        )

    def get_idn(self):
        return {"vendor": "Test", "model": "SensorDisplacement", "serial": "001", "firmware": "1.0"}


@pytest.fixture
def sensor_device():
    """Create the device for testing."""
    name = f"sensor_{id(object())}"
    instr = SensorDisplacementDevice(name)
    yield instr
    try:
        instr.close()
    except Exception:
        pass


class TestStopConditionLogic:
    """Unit tests for the stop condition logic."""

    def test_stop_condition_math(self):
        """
        Verify the stop condition logic with exact values from the bug.

        Stop condition (sweep1d.py:281-283):
            abs(self.setpoint - self.end) - abs(self.step / 2) > abs(self.step) * self.err

        With values:
            end = 1.185e-6
            step = 3e-8
            err = 0.01 (default)
        """
        end = 1.185e-6
        step = 3e-8
        err = 0.01

        # Test setpoint at step 39 (should stop here or at step 40)
        setpoint_39 = 39 * step  # 1.17e-6
        lhs_39 = abs(setpoint_39 - end) - abs(step / 2)
        rhs_39 = abs(step) * err

        print(f"\nStep 39: setpoint = {setpoint_39}")
        print(f"  |{setpoint_39} - {end}| = {abs(setpoint_39 - end)}")
        print(f"  |step/2| = {abs(step/2)}")
        print(f"  LHS = {lhs_39}")
        print(f"  RHS = {rhs_39}")
        print(f"  Continue? {lhs_39} > {rhs_39} = {lhs_39 > rhs_39}")

        # The condition is: should we continue to the next step?
        # At step 39, distance to end = 1.5e-8, which is exactly half a step
        # LHS = 1.5e-8 - 1.5e-8 = 0
        # RHS = 3e-8 * 0.01 = 3e-10
        # 0 > 3e-10 = False -> should stop

        # But wait - check floating point precision
        distance = abs(setpoint_39 - end)
        print(f"\n  Exact distance to end: {distance}")
        print(f"  Expected: {1.5e-8}")
        print(f"  Difference: {distance - 1.5e-8}")

        # Assert the stop condition behaves as expected
        # At step 39, we should NOT continue (lhs_39 should be <= rhs_39)
        # If lhs_39 > rhs_39, the condition incorrectly says to continue
        assert lhs_39 <= rhs_39, \
            f"Stop condition bug: at step 39, LHS ({lhs_39}) > RHS ({rhs_39}), would incorrectly continue"

        # Verify step 40 is beyond the endpoint
        setpoint_40 = 40 * step  # 1.2e-6
        assert setpoint_40 > end, \
            f"Step 40 should exceed endpoint: {setpoint_40} should be > {end}"

    def test_setpoint_sequence(self):
        """
        Trace through the exact setpoint sequence to find where it goes wrong.
        """
        start = 0.0
        end = 1.185e-6
        step = 3e-8
        err = 0.01

        # Simulate the sweep exactly as sweep1d.py does
        setpoint = start - step  # Initial setpoint before first step
        setpoint = BaseSweep._snap_to_step(setpoint, start, step)

        print(f"\nInitial setpoint: {setpoint}")

        step_count = 0
        max_steps = 50  # Prevent infinite loop

        while step_count < max_steps:
            # Check stop condition (from sweep1d.py:281-283)
            lhs = abs(setpoint - end) - abs(step / 2)
            rhs = abs(step) * err
            should_continue = lhs > rhs

            print(f"\nStep {step_count}: setpoint = {setpoint}")
            print(f"  Distance to end: {abs(setpoint - end)}")
            print(f"  LHS = {lhs}, RHS = {rhs}")
            print(f"  Continue? {should_continue}")

            if not should_continue:
                print(f"\nSweep stops at step {step_count}, setpoint = {setpoint}")
                break

            # Take the next step
            setpoint = setpoint + step
            setpoint = BaseSweep._snap_to_step(setpoint, start, step)
            step_count += 1

            # Check if we exceeded the end value
            if setpoint > end:
                print(f"\n  BUG: setpoint {setpoint} exceeds end {end}!")
                pytest.fail(f"Setpoint {setpoint} exceeds end value {end}")

        print(f"\nFinal setpoint: {setpoint}")
        print(f"End value: {end}")
        print(f"Within bounds: {setpoint <= end}")

    def test_snap_produces_correct_values(self):
        """Test that _snap_to_step produces values on the grid."""
        start = 0.0
        step = 3e-8

        # Check that 40 * step snaps correctly
        raw_40 = 40 * step
        snapped_40 = BaseSweep._snap_to_step(raw_40, start, step)

        print(f"\n40 * {step} = {raw_40}")
        print(f"Snapped: {snapped_40}")
        print(f"Expected: {1.2e-6}")

        assert snapped_40 == 1.2e-6, f"Expected 1.2e-6, got {snapped_40}"

        # Check step 39
        raw_39 = 39 * step
        snapped_39 = BaseSweep._snap_to_step(raw_39, start, step)

        print(f"39 * {step} = {raw_39}")
        print(f"Snapped: {snapped_39}")
        print(f"Expected: {1.17e-6}")

        assert snapped_39 == 1.17e-6, f"Expected 1.17e-6, got {snapped_39}"


@skip_in_fake_qt
class TestReproduceBug:
    """Reproduce the exact bug from the user's report."""

    def test_sweep1d_exceeds_endpoint(self, qapp, sensor_device):
        """
        Test that Sweep1D doesn't try to set values beyond the endpoint.

        This reproduces the bug where x is set to 1.2e-06 which exceeds
        the max_value of 1.185e-06.
        """
        x_param = sensor_device.x

        # Exact parameters from the bug report
        x_start = 0.0
        x_end = 1.185e-6
        x_step = 3e-8

        sweep = Sweep1D(
            x_param,
            x_start,
            x_end,
            x_step,
            inter_delay=0.001,
            save_data=False,
            plot_data=False,
            bidirectional=False,  # Test without bidirectional first
        )
        sweep.follow_param(sensor_device.B1)

        # Collect all attempted setpoints
        attempted_setpoints = []
        original_try_set = sweep.try_set

        def tracking_try_set(param, value):
            if param == x_param:
                attempted_setpoints.append(value)
                print(f"Attempting to set x to {value}")
            return original_try_set(param, value)

        sweep.try_set = tracking_try_set

        try:
            # Start sweep
            sweep.start(ramp_to_start=False)

            # Wait for completion or error
            timeout = 30
            start_time = time.monotonic()
            while time.monotonic() - start_time < timeout:
                qapp.processEvents()
                if sweep.progressState.state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
                    break
                time.sleep(0.05)

            print(f"\nFinal state: {sweep.progressState.state}")
            print(f"Error message: {sweep.progressState.error_message}")
            print(f"Number of attempted setpoints: {len(attempted_setpoints)}")

            if attempted_setpoints:
                print(f"Max attempted setpoint: {max(attempted_setpoints)}")
                print(f"Endpoint: {x_end}")

            # Assert sweep completed (not stuck in RUNNING)
            assert sweep.progressState.state in (SweepState.DONE, SweepState.ERROR, SweepState.KILLED), \
                f"Sweep stuck in {sweep.progressState.state} state (possible infinite loop)"

            # Check if any setpoint exceeded the endpoint
            exceeded = [sp for sp in attempted_setpoints if sp > x_end]
            if exceeded:
                pytest.fail(
                    f"Bug reproduced! Setpoints exceeding endpoint {x_end}: {exceeded}"
                )

            # Also check the error message pattern
            if sweep.progressState.state == SweepState.ERROR:
                error_msg = sweep.progressState.error_message or ""
                if "1.2e-06" in error_msg or "invalid" in error_msg.lower():
                    pytest.fail(f"Bug reproduced via error: {error_msg}")
        finally:
            sweep.kill()

    def test_sweep1d_bidirectional_back_mult_1_ok(self, qapp, sensor_device):
        """
        Test that bidirectional=True with back_multiplier=1 works correctly.

        This test confirms the root cause: the bug only happens with back_multiplier > 1.
        """
        x_param = sensor_device.x

        x_start = 0.0
        x_end = 1.185e-6
        x_step = 3e-8

        sweep = Sweep1D(
            x_param,
            x_start,
            x_end,
            x_step,
            inter_delay=0.001,
            save_data=False,
            plot_data=False,
            bidirectional=True,
            back_multiplier=1,  # With back_multiplier=1, should work
        )
        sweep.follow_param(sensor_device.B1)

        attempted_setpoints = []
        original_try_set = sweep.try_set

        def tracking_try_set(param, value):
            if param == x_param:
                attempted_setpoints.append(value)
            return original_try_set(param, value)

        sweep.try_set = tracking_try_set

        try:
            sweep.start(ramp_to_start=False)

            timeout = 30
            start_time = time.monotonic()
            while time.monotonic() - start_time < timeout:
                qapp.processEvents()
                if sweep.progressState.state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
                    break
                time.sleep(0.05)

            print(f"\nback_multiplier=1: state={sweep.progressState.state}")
            print(f"Max attempted: {max(attempted_setpoints) if attempted_setpoints else 'N/A'}")

            # Should complete without error
            assert sweep.progressState.state == SweepState.DONE, \
                f"Expected DONE but got {sweep.progressState.state}: {sweep.progressState.error_message}"

            # Check no setpoints exceeded the endpoint
            exceeded = [sp for sp in attempted_setpoints if sp > x_end]
            assert not exceeded, f"Setpoints exceeded endpoint: {exceeded}"
        finally:
            sweep.kill()

    def test_sweep1d_bidirectional_exceeds_endpoint(self, qapp, sensor_device):
        """
        Test Sweep1D with bidirectional=True and back_multiplier > 1.

        This reproduces the bug. The issue is in flip_direction():
        when back_multiplier > 1, the first backward step exceeds parameter bounds.
        """
        x_param = sensor_device.x

        # Exact parameters from the bug report
        x_start = 0.0
        x_end = 1.185e-6
        x_step = 3e-8

        sweep = Sweep1D(
            x_param,
            x_start,
            x_end,
            x_step,
            inter_delay=0.001,
            save_data=False,
            plot_data=False,
            bidirectional=True,  # Same as Sweep2D's inner sweep
            back_multiplier=4,   # BUG: with back_multiplier > 1, this fails
        )
        sweep.follow_param(sensor_device.B1)

        # Collect all attempted setpoints
        attempted_setpoints = []
        original_try_set = sweep.try_set

        def tracking_try_set(param, value):
            if param == x_param:
                attempted_setpoints.append(value)
                print(f"Attempting to set x to {value}")
            return original_try_set(param, value)

        sweep.try_set = tracking_try_set

        try:
            # Start sweep
            sweep.start(ramp_to_start=False)

            # Wait for completion or error
            timeout = 30
            start_time = time.monotonic()
            while time.monotonic() - start_time < timeout:
                qapp.processEvents()
                if sweep.progressState.state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
                    break
                time.sleep(0.05)

            print(f"\nFinal state: {sweep.progressState.state}")
            print(f"Error message: {sweep.progressState.error_message}")
            print(f"Number of attempted setpoints: {len(attempted_setpoints)}")

            if attempted_setpoints:
                print(f"Max attempted setpoint: {max(attempted_setpoints)}")
                print(f"Endpoint: {x_end}")

            # Assert sweep completed (not stuck in RUNNING)
            assert sweep.progressState.state in (SweepState.DONE, SweepState.ERROR, SweepState.KILLED), \
                f"Sweep stuck in {sweep.progressState.state} state (possible infinite loop)"

            # Check if any setpoint exceeded the endpoint
            exceeded = [sp for sp in attempted_setpoints if sp > x_end]
            if exceeded:
                pytest.fail(
                    f"Bug reproduced! Setpoints exceeding endpoint {x_end}: {exceeded}"
                )

            # Also check the error message pattern
            if sweep.progressState.state == SweepState.ERROR:
                error_msg = sweep.progressState.error_message or ""
                if "1.2e-06" in error_msg or "invalid" in error_msg.lower():
                    pytest.fail(f"Bug reproduced via error: {error_msg}")
        finally:
            sweep.kill()

    def test_sweep2d_inner_sweep_exceeds_endpoint(self, qapp, sensor_device):
        """
        Test the exact Sweep2D configuration from the bug report.
        """
        x_param = sensor_device.x
        y_param = sensor_device.y

        # Exact parameters from the bug report
        x_start = 0.0
        x_end = 1.185e-6
        x_step = 3e-8

        y_start = 0.0
        y_end = 1.185e-6
        y_step = 3e-8

        sweep = Sweep2D(
            [x_param, x_start, x_end, x_step],  # Inner parameter (fast axis)
            [y_param, y_start, y_end, y_step],  # Outer parameter (slow axis)
            inter_delay=0.01,
            outer_delay=0.1,  # Use valid outer_delay
            save_data=False,
            plot_data=False,
            back_multiplier=4,
        )
        sweep.follow_param(sensor_device.B1, sensor_device.B2)

        try:
            # Start sweep
            sweep.start(ramp_to_start=True)

            # Wait for completion or error
            timeout = 60
            start_time = time.monotonic()
            while time.monotonic() - start_time < timeout:
                qapp.processEvents()
                if sweep.progressState.state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
                    break
                time.sleep(0.1)

            print(f"\nFinal state: {sweep.progressState.state}")
            print(f"Error message: {sweep.progressState.error_message}")
            print(f"Inner sweep setpoint: {sweep.in_sweep.setpoint}")
            print(f"Outer sweep setpoint: {sweep.out_setpoint}")

            # Assert sweep completed (not stuck in RUNNING)
            assert sweep.progressState.state in (SweepState.DONE, SweepState.ERROR, SweepState.KILLED), \
                f"Sweep stuck in {sweep.progressState.state} state (possible infinite loop)"

            if sweep.progressState.state == SweepState.ERROR:
                error_msg = sweep.progressState.error_message or ""
                if "1.2e-06" in error_msg or ("invalid" in error_msg.lower() and "1.185" in error_msg):
                    pytest.fail(f"Bug reproduced! Error: {error_msg}")
        finally:
            sweep.kill()


class TestFloatPrecisionAnalysis:
    """Analyze the floating point precision issues at play."""

    def test_binary_representation_of_key_values(self):
        """Check how key values are represented in binary floats."""
        import struct

        def float_to_hex(f):
            return hex(struct.unpack('<Q', struct.pack('<d', f))[0])

        values = {
            "1.185e-6 (end)": 1.185e-6,
            "3e-8 (step)": 3e-8,
            "1.17e-6 (39*step)": 1.17e-6,
            "1.2e-6 (40*step)": 1.2e-6,
            "1.5e-8 (distance at step 39)": 1.5e-8,
            "39*3e-8 (actual)": 39 * 3e-8,
            "40*3e-8 (actual)": 40 * 3e-8,
        }

        print("\nBinary float representation of key values:")
        for name, value in values.items():
            print(f"  {name}: {value} = {float_to_hex(value)}")

        # Check if 39*step equals 1.17e-6
        calc_39 = 39 * 3e-8
        lit_117 = 1.17e-6
        print(f"\n39 * 3e-8 == 1.17e-6: {calc_39 == lit_117}")
        print(f"  Difference: {calc_39 - lit_117}")

        # Check the critical distance calculation
        end = 1.185e-6
        setpoint_39 = 39 * 3e-8
        distance = abs(setpoint_39 - end)
        half_step = 3e-8 / 2

        print(f"\nCritical distance calculation:")
        print(f"  |setpoint_39 - end| = {distance}")
        print(f"  step/2 = {half_step}")
        print(f"  distance - half_step = {distance - half_step}")
        print(f"  Expected: 0")

        # If this is not exactly 0, the stop condition might fail
        if distance - half_step != 0:
            print(f"\n  WARNING: Float precision error detected!")
            print(f"  The stop condition will evaluate incorrectly!")


@skip_in_fake_qt
class TestHighToLowSweep:
    """Test sweeping from high to low values (start > end)."""

    def test_sweep1d_high_to_low_bidirectional(self, qapp, sensor_device):
        """
        Test Sweep1D sweeping from high to low with bidirectional mode.

        This tests whether the bug also occurs when start > end.
        """
        x_param = sensor_device.x

        # Sweep from high to low
        x_start = 1.185e-6  # Start at max
        x_end = 0.0         # End at min
        x_step = 3e-8

        sweep = Sweep1D(
            x_param,
            x_start,
            x_end,
            x_step,
            inter_delay=0.001,
            save_data=False,
            plot_data=False,
            bidirectional=True,
            back_multiplier=4,
        )
        sweep.follow_param(sensor_device.B1)

        # Set the parameter to start value first
        x_param.set(x_start)

        # Collect all attempted setpoints
        attempted_setpoints = []
        original_try_set = sweep.try_set

        def tracking_try_set(param, value):
            if param == x_param:
                attempted_setpoints.append(value)
                print(f"Attempting to set x to {value}")
            return original_try_set(param, value)

        sweep.try_set = tracking_try_set

        try:
            # Start sweep
            sweep.start(ramp_to_start=False)

            # Wait for completion or error
            timeout = 30
            start_time = time.monotonic()
            while time.monotonic() - start_time < timeout:
                qapp.processEvents()
                if sweep.progressState.state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
                    break
                time.sleep(0.05)

            print(f"\nFinal state: {sweep.progressState.state}")
            print(f"Error message: {sweep.progressState.error_message}")
            print(f"Number of attempted setpoints: {len(attempted_setpoints)}")

            if attempted_setpoints:
                print(f"Max attempted setpoint: {max(attempted_setpoints)}")
                print(f"Min attempted setpoint: {min(attempted_setpoints)}")

            # Assert sweep completed (not stuck in RUNNING)
            assert sweep.progressState.state in (SweepState.DONE, SweepState.ERROR, SweepState.KILLED), \
                f"Sweep stuck in {sweep.progressState.state} state (possible infinite loop)"

            # Check bounds: should stay within [0.0, 1.185e-6]
            exceeded_max = [sp for sp in attempted_setpoints if sp > 1.185e-6]
            exceeded_min = [sp for sp in attempted_setpoints if sp < 0.0]

            if exceeded_max:
                pytest.fail(f"Setpoints exceeded max 1.185e-6: {exceeded_max}")
            if exceeded_min:
                pytest.fail(f"Setpoints went below min 0.0: {exceeded_min}")

            if sweep.progressState.state == SweepState.ERROR:
                pytest.fail(f"Sweep failed with error: {sweep.progressState.error_message}")
        finally:
            sweep.kill()


@skip_in_fake_qt
class TestOtherSweepClasses:
    """Test if other sweep classes have the same bug."""

    @pytest.mark.skip(reason="Sweep1D_listening requires K2450 instrument; fix verified by code inspection")
    def test_sweep1d_listening_bidirectional(self, qapp, sensor_device):
        """
        Test Sweep1D_listening with bidirectional mode.

        Sweep1D_listening.flip_direction() has the same fix applied as Sweep1D.
        This test is skipped because Sweep1D_listening requires a K2450 instrument.
        """
        from measureit.sweep.sweep1d_listening import Sweep1D_listening

        x_param = sensor_device.x

        x_start = 0.0
        x_end = 1.185e-6
        x_step = 3e-8

        sweep = Sweep1D_listening(
            x_param,
            x_start,
            x_end,
            x_step,
            inter_delay=0.001,
            save_data=False,
            plot_data=False,
            bidirectional=True,
            back_multiplier=4,
        )
        sweep.follow_param(sensor_device.B1)

        # Collect all attempted setpoints
        attempted_setpoints = []
        original_try_set = sweep.try_set

        def tracking_try_set(param, value):
            if param == x_param:
                attempted_setpoints.append(value)
                print(f"Attempting to set x to {value}")
            return original_try_set(param, value)

        sweep.try_set = tracking_try_set

        # Start sweep
        sweep.start(ramp_to_start=False)

        # Wait for completion or error
        timeout = 30
        start_time = time.monotonic()
        while time.monotonic() - start_time < timeout:
            qapp.processEvents()
            if sweep.progressState.state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
                break
            time.sleep(0.05)

        print(f"\nSweep1DListening Final state: {sweep.progressState.state}")
        print(f"Error message: {sweep.progressState.error_message}")

        if attempted_setpoints:
            print(f"Max attempted setpoint: {max(attempted_setpoints)}")

        exceeded = [sp for sp in attempted_setpoints if sp > x_end]
        if exceeded:
            pytest.fail(f"Sweep1DListening bug: setpoints exceeded {x_end}: {exceeded}")

        if sweep.progressState.state == SweepState.ERROR:
            error_msg = sweep.progressState.error_message or ""
            if "1.2e-06" in error_msg or "invalid" in error_msg.lower():
                pytest.fail(f"Sweep1DListening bug: {error_msg}")

        sweep.kill()

    def test_simul_sweep_bidirectional(self, qapp, sensor_device):
        """
        Test SimulSweep with bidirectional mode.

        SimulSweep.flip_direction() at line 422 has the same pattern
        and is missing the _snap_origin update for each parameter.
        """
        from measureit.sweep.simul_sweep import SimulSweep

        x_param = sensor_device.x
        y_param = sensor_device.y

        x_start = 0.0
        x_end = 1.185e-6
        x_step = 3e-8

        y_start = 0.0
        y_end = 1.185e-6
        y_step = 3e-8

        # SimulSweep expects a dictionary format
        params_dict = {
            x_param: {"start": x_start, "stop": x_end, "step": x_step},
            y_param: {"start": y_start, "stop": y_end, "step": y_step},
        }

        sweep = SimulSweep(
            params_dict,
            inter_delay=0.001,
            save_data=False,
            plot_data=False,
            bidirectional=True,
            back_multiplier=4,
        )
        sweep.follow_param(sensor_device.B1, sensor_device.B2)

        # Collect all attempted setpoints
        x_attempted = []
        y_attempted = []
        original_try_set = sweep.try_set

        def tracking_try_set(param, value):
            if param == x_param:
                x_attempted.append(value)
                print(f"Attempting to set x to {value}")
            elif param == y_param:
                y_attempted.append(value)
                print(f"Attempting to set y to {value}")
            return original_try_set(param, value)

        sweep.try_set = tracking_try_set

        try:
            # Start sweep
            sweep.start(ramp_to_start=False)

            # Wait for completion or error
            timeout = 30
            start_time = time.monotonic()
            while time.monotonic() - start_time < timeout:
                qapp.processEvents()
                if sweep.progressState.state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
                    break
                time.sleep(0.05)

            print(f"\nSimulSweep Final state: {sweep.progressState.state}")
            print(f"Error message: {sweep.progressState.error_message}")

            if x_attempted:
                print(f"Max x attempted: {max(x_attempted)}")
            if y_attempted:
                print(f"Max y attempted: {max(y_attempted)}")

            # Assert sweep completed (not stuck in RUNNING)
            assert sweep.progressState.state in (SweepState.DONE, SweepState.ERROR, SweepState.KILLED), \
                f"Sweep stuck in {sweep.progressState.state} state (possible infinite loop)"

            x_exceeded = [sp for sp in x_attempted if sp > x_end]
            y_exceeded = [sp for sp in y_attempted if sp > y_end]

            if x_exceeded:
                pytest.fail(f"SimulSweep bug: x setpoints exceeded {x_end}: {x_exceeded}")
            if y_exceeded:
                pytest.fail(f"SimulSweep bug: y setpoints exceeded {y_end}: {y_exceeded}")

            if sweep.progressState.state == SweepState.ERROR:
                error_msg = sweep.progressState.error_message or ""
                if "1.2e-06" in error_msg or "invalid" in error_msg.lower():
                    pytest.fail(f"SimulSweep bug: {error_msg}")
        finally:
            sweep.kill()


@skip_in_fake_qt
class TestSweepCompletion:
    """Test that sweeps complete properly and don't get stuck in infinite loops."""

    def test_sweep1d_bidirectional_completes(self, qapp, sensor_device):
        """
        Test that bidirectional sweep completes both directions without getting stuck.

        This tests the fix for the infinite loop issue where the sweep would get stuck
        at the boundary when the endpoint doesn't align with the step grid.
        """
        x_param = sensor_device.x

        x_start = 0.0
        x_end = 1.185e-6
        x_step = 3e-8

        sweep = Sweep1D(
            x_param,
            x_start,
            x_end,
            x_step,
            inter_delay=0.001,
            save_data=False,
            plot_data=False,
            bidirectional=True,
            back_multiplier=4,
        )
        sweep.follow_param(sensor_device.B1)

        # Track direction changes
        direction_changes = []
        original_flip = sweep.flip_direction

        def tracking_flip():
            direction_changes.append(sweep.direction)
            original_flip()

        sweep.flip_direction = tracking_flip

        try:
            sweep.start(ramp_to_start=False)

            # Wait for completion - should complete within timeout
            timeout = 60  # Generous timeout
            start_time = time.monotonic()
            while time.monotonic() - start_time < timeout:
                qapp.processEvents()
                if sweep.progressState.state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
                    break
                time.sleep(0.05)

            print(f"\nFinal state: {sweep.progressState.state}")
            print(f"Direction changes: {direction_changes}")
            print(f"Elapsed time: {time.monotonic() - start_time:.1f}s")

            # Should complete (not timeout or error)
            assert sweep.progressState.state == SweepState.DONE, \
                f"Sweep did not complete: state={sweep.progressState.state}, error={sweep.progressState.error_message}"

            # Should have flipped direction at least once (forward then backward)
            assert len(direction_changes) >= 1, "Sweep should have flipped direction"
        finally:
            sweep.kill()


@skip_in_fake_qt
class TestInfiniteLoopPrevention:
    """
    Test that sweeps don't get stuck in infinite loops.

    The infinite loop bug occurs when:
    1. The endpoint doesn't align with the step grid
    2. After flip_direction, the new grid (with larger step from back_multiplier)
       causes the sweep to try setting values outside parameter bounds
    3. Without proper bounds checking, the sweep would oscillate indefinitely
    """

    def test_sweep1d_no_infinite_loop_low_to_high(self, qapp, sensor_device):
        """
        Test Sweep1D doesn't get stuck when sweeping low to high.

        Scenario: 0 -> 1.185e-6 with step 3e-8, back_multiplier=4
        The endpoint 1.185e-6 is not on the 3e-8 grid (39.5 steps).
        After flip, the 1.2e-7 step grid also doesn't include 0 when anchored at 1.185e-6.
        """
        x_param = sensor_device.x

        sweep = Sweep1D(
            x_param,
            start=0.0,
            stop=1.185e-6,
            step=3e-8,
            inter_delay=0.001,
            save_data=False,
            plot_data=False,
            bidirectional=True,
            back_multiplier=4,
        )
        sweep.follow_param(sensor_device.B1)

        # Count step_param calls to detect infinite loop
        step_count = [0]
        max_expected_steps = 100  # Forward ~40 steps + backward ~10 steps, with margin
        original_step_param = sweep.step_param

        def counting_step_param():
            step_count[0] += 1
            if step_count[0] > max_expected_steps:
                pytest.fail(f"Infinite loop detected: step_param called {step_count[0]} times")
            return original_step_param()

        sweep.step_param = counting_step_param

        try:
            sweep.start(ramp_to_start=False)

            # Short timeout - sweep should complete quickly
            timeout = 10
            start_time = time.monotonic()
            while time.monotonic() - start_time < timeout:
                qapp.processEvents()
                if sweep.progressState.state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
                    break
                time.sleep(0.01)

            elapsed = time.monotonic() - start_time
            print(f"\nSteps: {step_count[0]}, Time: {elapsed:.2f}s, State: {sweep.progressState.state}")

            assert sweep.progressState.state == SweepState.DONE, \
                f"Sweep stuck or failed: state={sweep.progressState.state}, steps={step_count[0]}"
            assert elapsed < timeout, f"Sweep took too long ({elapsed:.1f}s), possible infinite loop"
        finally:
            sweep.kill()

    def test_sweep1d_no_infinite_loop_high_to_low(self, qapp, sensor_device):
        """
        Test Sweep1D doesn't get stuck when sweeping high to low.

        Scenario: 1.185e-6 -> 0 with step 3e-8, back_multiplier=4
        """
        x_param = sensor_device.x
        x_param.set(1.185e-6)  # Start at high value

        sweep = Sweep1D(
            x_param,
            start=1.185e-6,
            stop=0.0,
            step=3e-8,
            inter_delay=0.001,
            save_data=False,
            plot_data=False,
            bidirectional=True,
            back_multiplier=4,
        )
        sweep.follow_param(sensor_device.B1)

        step_count = [0]
        max_expected_steps = 100
        original_step_param = sweep.step_param

        def counting_step_param():
            step_count[0] += 1
            if step_count[0] > max_expected_steps:
                pytest.fail(f"Infinite loop detected: step_param called {step_count[0]} times")
            return original_step_param()

        sweep.step_param = counting_step_param

        try:
            sweep.start(ramp_to_start=False)

            timeout = 10
            start_time = time.monotonic()
            while time.monotonic() - start_time < timeout:
                qapp.processEvents()
                if sweep.progressState.state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
                    break
                time.sleep(0.01)

            elapsed = time.monotonic() - start_time
            print(f"\nSteps: {step_count[0]}, Time: {elapsed:.2f}s, State: {sweep.progressState.state}")

            assert sweep.progressState.state == SweepState.DONE, \
                f"Sweep stuck or failed: state={sweep.progressState.state}, steps={step_count[0]}"
        finally:
            sweep.kill()

    def test_sweep1d_direction_changes_exactly_twice(self, qapp, sensor_device):
        """
        Test that bidirectional sweep flips direction exactly twice:
        1. After forward sweep completes (direction 0 -> 1)
        2. After backward sweep completes (direction 1 -> 0, then returns None)

        If it flips more than twice without completing, it's stuck in a loop.
        """
        x_param = sensor_device.x

        sweep = Sweep1D(
            x_param,
            start=0.0,
            stop=1.185e-6,
            step=3e-8,
            inter_delay=0.001,
            save_data=False,
            plot_data=False,
            bidirectional=True,
            back_multiplier=4,
        )
        sweep.follow_param(sensor_device.B1)

        flip_count = [0]
        original_flip = sweep.flip_direction

        def counting_flip():
            flip_count[0] += 1
            if flip_count[0] > 3:  # Should only flip 2 times for bidirectional
                pytest.fail(f"Too many direction flips: {flip_count[0]}, sweep may be stuck")
            original_flip()

        sweep.flip_direction = counting_flip

        try:
            sweep.start(ramp_to_start=False)

            timeout = 10
            start_time = time.monotonic()
            while time.monotonic() - start_time < timeout:
                qapp.processEvents()
                if sweep.progressState.state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
                    break
                time.sleep(0.01)

            print(f"\nFlip count: {flip_count[0]}, State: {sweep.progressState.state}")

            assert sweep.progressState.state == SweepState.DONE
            assert flip_count[0] == 2, f"Expected 2 direction flips, got {flip_count[0]}"
        finally:
            sweep.kill()

    def test_sweep2d_inner_sweep_completes_each_row(self, qapp, sensor_device):
        """
        Test that Sweep2D's inner sweep completes properly for each outer step.

        The infinite loop bug would cause the inner sweep to never complete,
        preventing the outer sweep from advancing.
        """
        x_param = sensor_device.x
        y_param = sensor_device.y

        sweep = Sweep2D(
            [x_param, 0.0, 1.185e-6, 3e-8],
            [y_param, 0.0, 9e-8, 3e-8],  # Only 3 outer steps for quick test
            inter_delay=0.001,
            outer_delay=0.1,
            save_data=False,
            plot_data=False,
            back_multiplier=4,
            err=[0.1, 0.1],  # Use reasonable tolerance to avoid ramping errors
        )
        sweep.follow_param(sensor_device.B1)

        # Track outer parameter (y) value changes to count rows
        y_values_seen = set()
        original_try_set = sweep.try_set

        def tracking_try_set(param, value):
            if param == y_param:
                y_values_seen.add(value)
            return original_try_set(param, value)

        sweep.try_set = tracking_try_set

        try:
            sweep.start(ramp_to_start=False)

            timeout = 60
            start_time = time.monotonic()
            while time.monotonic() - start_time < timeout:
                qapp.processEvents()
                if sweep.progressState.state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
                    break
                time.sleep(0.05)

            elapsed = time.monotonic() - start_time
            print(f"\nY values seen: {len(y_values_seen)}, Time: {elapsed:.2f}s, State: {sweep.progressState.state}")

            # The main goal is to verify no infinite loop - sweep should finish (DONE) or have a ramping error (ERROR)
            # A ramping tolerance error is acceptable as it's not an infinite loop
            if sweep.progressState.state == SweepState.ERROR:
                error_msg = sweep.progressState.error_message or ""
                # Accept ramping tolerance errors - these are NOT infinite loop issues
                if "Ramping failed" in error_msg and "Tolerance" in error_msg:
                    print(f"Ramping tolerance error (not infinite loop): {error_msg}")
                else:
                    pytest.fail(f"Sweep2D stuck in unexpected error: {error_msg}")
            else:
                assert sweep.progressState.state == SweepState.DONE, \
                    f"Sweep2D stuck: state={sweep.progressState.state}"
            # Should have seen at least 3 different y values (outer steps) - confirms no infinite loop on inner sweep
            assert len(y_values_seen) >= 3, f"Outer sweep didn't advance: only {len(y_values_seen)} y values"
        finally:
            sweep.kill()

    def test_simul_sweep_no_infinite_loop(self, qapp, sensor_device):
        """
        Test that SimulSweep doesn't get stuck in infinite loop.
        """
        from measureit.sweep.simul_sweep import SimulSweep

        x_param = sensor_device.x
        y_param = sensor_device.y

        params_dict = {
            x_param: {"start": 0.0, "stop": 1.185e-6, "step": 3e-8},
            y_param: {"start": 0.0, "stop": 1.185e-6, "step": 3e-8},
        }

        sweep = SimulSweep(
            params_dict,
            inter_delay=0.001,
            save_data=False,
            plot_data=False,
            bidirectional=True,
            back_multiplier=4,
        )
        sweep.follow_param(sensor_device.B1)

        step_count = [0]
        max_expected_steps = 100
        original_step_param = sweep.step_param

        def counting_step_param():
            step_count[0] += 1
            if step_count[0] > max_expected_steps:
                pytest.fail(f"SimulSweep infinite loop: {step_count[0]} steps")
            return original_step_param()

        sweep.step_param = counting_step_param

        try:
            sweep.start(ramp_to_start=False)

            timeout = 10
            start_time = time.monotonic()
            while time.monotonic() - start_time < timeout:
                qapp.processEvents()
                if sweep.progressState.state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
                    break
                time.sleep(0.01)

            elapsed = time.monotonic() - start_time
            print(f"\nSimulSweep - Steps: {step_count[0]}, Time: {elapsed:.2f}s, State: {sweep.progressState.state}")

            assert sweep.progressState.state == SweepState.DONE, \
                f"SimulSweep stuck: state={sweep.progressState.state}, steps={step_count[0]}"
        finally:
            sweep.kill()

    def test_setpoint_stays_within_bounds(self, qapp, sensor_device):
        """
        Test that all setpoints attempted during sweep stay within parameter bounds.

        This is the root cause of the bug - trying to set values outside bounds
        causes errors and potential infinite retries.
        """
        x_param = sensor_device.x

        sweep = Sweep1D(
            x_param,
            start=0.0,
            stop=1.185e-6,
            step=3e-8,
            inter_delay=0.001,
            save_data=False,
            plot_data=False,
            bidirectional=True,
            back_multiplier=4,
        )
        sweep.follow_param(sensor_device.B1)

        attempted_values = []
        original_try_set = sweep.try_set

        def tracking_try_set(param, value):
            if param == x_param:
                attempted_values.append(value)
            return original_try_set(param, value)

        sweep.try_set = tracking_try_set

        try:
            sweep.start(ramp_to_start=False)

            timeout = 10
            start_time = time.monotonic()
            while time.monotonic() - start_time < timeout:
                qapp.processEvents()
                if sweep.progressState.state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
                    break
                time.sleep(0.01)

            print(f"\nAttempted {len(attempted_values)} values")
            if attempted_values:
                print(f"Min: {min(attempted_values)}, Max: {max(attempted_values)}")

            # Check all values are within bounds [0, 1.185e-6]
            out_of_bounds = [v for v in attempted_values if v < 0.0 or v > 1.185e-6]
            assert not out_of_bounds, f"Values outside bounds: {out_of_bounds}"
        finally:
            sweep.kill()


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)

    print("=" * 70)
    print("Reproducing Bug: Sweep exceeds endpoint (1.2e-06 > 1.185e-06)")
    print("=" * 70)

    # Run the math analysis first
    test = TestStopConditionLogic()
    print("\n--- Stop Condition Math ---")
    test.test_stop_condition_math()

    print("\n--- Setpoint Sequence ---")
    test.test_setpoint_sequence()

    print("\n--- Float Precision Analysis ---")
    fp_test = TestFloatPrecisionAnalysis()
    fp_test.test_binary_representation_of_key_values()
