#!/usr/bin/env python3
"""
Manual test script to verify Sweep2D with nanoscale parameters.
Mimics the user's AFM scan scenario.

Run with: source activate instrMCPdev && python tests/manual/test_afm_sweep2d.py
"""

import sys
import time

# Add src to path
sys.path.insert(0, "src")

from PyQt5.QtWidgets import QApplication
from qcodes.instrument import Instrument
from qcodes.validators import Numbers

from measureit.sweep.sweep2d import Sweep2D
from measureit.sweep.progress import SweepState


class MockAFMInstrument(Instrument):
    """Mock AFM instrument with x, y, and b parameters."""

    def __init__(self, name):
        super().__init__(name)

        # x parameter: validation 0 to 9.9e-7
        self.add_parameter(
            "x",
            unit="m",
            label="Scan position x",
            vals=Numbers(min_value=0.0, max_value=9.9e-7),
            set_cmd=None,
            get_cmd=None,
            initial_value=0.0,
        )

        # y parameter: validation 0 to 9.9e-7
        self.add_parameter(
            "y",
            unit="m",
            label="Scan position y",
            vals=Numbers(min_value=0.0, max_value=9.9e-7),
            set_cmd=None,
            get_cmd=None,
            initial_value=0.0,
        )

        # b parameter: magnetic field value to measure
        self._b_value = 0.0
        self.add_parameter(
            "b",
            unit="T",
            label="Magnetic field",
            set_cmd=None,
            get_cmd=self._get_b,
        )

    def _get_b(self):
        """Return a simulated magnetic field value based on position."""
        x = self.x.get()
        y = self.y.get()
        # Simulate some spatial variation
        import math
        return math.sin(x * 1e7) * math.cos(y * 1e7) * 1e-6

    def get_idn(self):
        return {"vendor": "Mock", "model": "AFM", "serial": "001", "firmware": "1.0"}


def main():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # Create mock instrument
    instr_name = f"mock_afm_{id(object())}"
    print(f"Creating mock instrument: {instr_name}")
    instr = MockAFMInstrument(instr_name)

    # Define sweep parameters (exactly like user's code)
    x_param = instr.x
    x_start = 0
    x_end = 9.0e-7  # 900 nm scan
    x_step = 1e-8   # 10 nm steps

    y_param = instr.y
    y_start = 0
    y_end = 9.0e-7  # 900 nm scan
    y_step = 1e-8   # 10 nm steps

    print(f"\nSweep2D Configuration:")
    print(f"  x: {x_start} to {x_end}, step {x_step}")
    print(f"  y: {y_start} to {y_end}, step {y_step}")
    print(f"  x validation: 0.0 to 9.9e-7")
    print(f"  y validation: 0.0 to 9.9e-7")

    # Create Sweep2D (x is outer, y is inner)
    sweep = Sweep2D(
        [x_param, x_start, x_end, x_step],
        [y_param, y_start, y_end, y_step],
        inter_delay=0.001,  # Fast for testing
        outer_delay=0.01,
        save_data=False,
        plot_data=False,
        err=[0.01, 0.01],
    )
    sweep.follow_param(instr.b)

    print("\nStarting sweep...")
    sweep.start(ramp_to_start=True)

    # Monitor the sweep
    timeout = 120  # 2 minutes max
    start_time = time.monotonic()
    last_x = None
    outer_steps = 0

    while time.monotonic() - start_time < timeout:
        app.processEvents()

        # Check state
        state = sweep.progressState.state
        if state in (SweepState.ERROR, SweepState.DONE, SweepState.KILLED):
            break

        # Monitor outer parameter progress
        current_x = sweep.out_setpoint
        if current_x != last_x:
            print(f"  Outer x = {current_x:.2e}, Inner state = {sweep.in_sweep.progressState.state.name}")
            last_x = current_x
            outer_steps += 1

        time.sleep(0.1)

    # Report results
    print(f"\n{'='*50}")
    print(f"Final state: {sweep.progressState.state.name}")
    print(f"Outer steps completed: {outer_steps}")
    print(f"Final x position: {sweep.out_setpoint:.2e}")
    print(f"Final y position: {instr.y.get():.2e}")

    if sweep.progressState.error_message:
        print(f"Error: {sweep.progressState.error_message}")

    if sweep.progressState.state == SweepState.ERROR:
        print("\n*** SWEEP FAILED ***")
        return 1
    elif sweep.progressState.state == SweepState.DONE:
        print("\n*** SWEEP COMPLETED SUCCESSFULLY ***")
        return 0
    else:
        print(f"\n*** SWEEP ENDED IN STATE: {sweep.progressState.state.name} ***")
        return 1

    sweep.kill()
    instr.close()


if __name__ == "__main__":
    sys.exit(main())
