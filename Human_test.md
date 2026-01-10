# Human Testing Guide: Error Handling with Mock Instruments

This guide documents how to run comprehensive tests for error handling in MeasureIt sweeps (Sweep0D, Sweep1D, Sweep2D, SimulSweep) and SweepQueue using mock instruments.

## Prerequisites

```bash
# Activate the conda environment
source ~/miniforge3/etc/profile.d/conda.sh && conda activate instrMCPdev
```

## Setup: Mock Instruments

MeasureIt uses QCoDeS `MockParabola` for testing. This mock instrument provides:
- Parameters: `x`, `y`, `z` (settable)
- Parameter: `parabola` (computed from x, y, z)
- Parameter: `noise` (configurable noise level)

### Basic Setup

```python
import qcodes as qc
from qcodes.instrument_drivers.mock_instruments import MockParabola

from measureit import Sweep0D, Sweep1D, Sweep2D, SimulSweep
from measureit.tools import ensure_qt, init_database
from measureit.tools.sweep_queue import SweepQueue, DatabaseEntry
from measureit.config import get_path

ensure_qt()

# Create mock instruments
instr0 = MockParabola(name="test_instrument0")
instr0.noise.set(3)
instr0.parabola.label = "Value of instr0"

instr1 = MockParabola(name="test_instrument1")
instr1.noise.set(10)
instr1.parabola.label = "Value of instr1"

# Define follow parameters
follow_params = {instr0.parabola, instr1.parabola}
```

---

## Error Handling Test Scenarios

### 1. Sweep0D Parameter Read Error

Tests that `safe_get()` properly raises `ParameterException` when a parameter read fails.

```python
from unittest.mock import patch, MagicMock
from measureit.sweep.progress import SweepState
from measureit.tools.util import ParameterException
from PyQt5.QtWidgets import QApplication
import time

# Create Sweep0D
s = Sweep0D(max_time=10, inter_delay=0.1, save_data=False, plot_data=True)
s.follow_param(instr0.parabola)

# Simulate parameter read failure
def failing_get():
    raise Exception("Communication timeout")

# Patch the parabola getter to fail
original_get = instr0.parabola.get
instr0.parabola.get = failing_get

try:
    s.start()

    # Wait for error to propagate:
    # - safe_get() tries once, fails, sleeps 1s, retries
    # - After 2nd failure, raises ParameterException
    # - Runner catches it and calls mark_error(_from_runner=True)
    # - Signal is queued via QMetaObject.invokeMethod
    # We need ~2.5s plus Qt event processing
    for _ in range(30):  # 30 * 0.1s = 3s timeout
        QApplication.processEvents()
        time.sleep(0.1)
        if s.progressState.state == SweepState.ERROR:
            break

    # Check if sweep transitioned to ERROR state
    print(f"Sweep state: {s.progressState.state}")
    print(f"Error message: {s.progressState.error_message}")

    if s.progressState.state == SweepState.ERROR:
        print("SUCCESS: Sweep0D correctly entered ERROR state on parameter read failure")
    else:
        print("NOTE: State is still", s.progressState.state)
        print("The error may still be propagating through the Qt event loop")
finally:
    instr0.parabola.get = original_get
    s.kill()
```
Result:
```
Sweep state: SweepState.ERROR
Error message: Parameter operation failed: Could not get parabola.
SUCCESS: Sweep0D correctly entered ERROR state on parameter read failure
```

### 2. Sweep1D Ramping Failure Error

Tests that ramping failures (position mismatch after ramp) transition to ERROR state.

```python
from measureit.sweep.progress import SweepState

# Create a Sweep1D
s = Sweep1D(
    instr0.x,
    start=0,
    stop=5,
    step=0.1,
    inter_delay=0.1,
    save_data=False,
    plot_data=True,
    bidirectional=False
)
s.follow_param(instr0.parabola)

# Manually test done_ramping with position mismatch
# First, set to a value different from expected
instr0.x.set(0.5)  # Set to 0.5

# Simulate ramping that ends at wrong position
s.progressState.state = SweepState.RAMPING

# Call done_ramping expecting value=0.0 but actual is 0.5
# This should trigger ERROR state
s.done_ramping(value=0.0, start_on_finish=False, pd=None)

print(f"Sweep state: {s.progressState.state}")
print(f"Error message: {s.progressState.error_message}")

if s.progressState.state == SweepState.ERROR:
    print("SUCCESS: Sweep1D correctly entered ERROR state on ramping failure")
    print("Error message mentions tolerance:", "tolerance" in s.progressState.error_message.lower())
else:
    print("FAILURE: Expected ERROR state")

s.kill()
```

Result:
```
Couldn't get parabola. Trying again. Communication timeout
Still couldn't get parabola. Giving up. Communication timeout
Sweep state: SweepState.ERROR
Error message: Parameter operation failed: Could not get parabola.
SUCCESS: Sweep0D correctly entered ERROR state on parameter read failure
```

### 3. Sweep1D Parameter Set Error During Sweep

Tests that `safe_set()` failures during stepping trigger ERROR state.

```python
from measureit.sweep.progress import SweepState

# Create a Sweep1D
s = Sweep1D(
    instr0.x,
    start=0,
    stop=5,
    step=0.1,
    inter_delay=0.1,
    save_data=False,
    plot_data=True
)
s.follow_param(instr0.parabola)

# Patch the set method to fail after a few successful sets
original_set = instr0.x.set
call_count = [0]

def failing_set_after_n(value):
    call_count[0] += 1
    if call_count[0] > 5:  # Fail after 5 successful sets
        raise Exception("Parameter validation failed: value out of range")
    return original_set(value)

instr0.x.set = failing_set_after_n

try:
    s.start(ramp_to_start=False)

    # Wait for error to occur
    import time
    time.sleep(2)

    print(f"Sweep state: {s.progressState.state}")
    print(f"Error message: {s.progressState.error_message}")
    print(f"Set calls before failure: {call_count[0]}")

    if s.progressState.state == SweepState.ERROR:
        print("SUCCESS: Sweep1D correctly entered ERROR state on set failure")
    else:
        print(f"FAILURE: Expected ERROR state, got {s.progressState.state}")
finally:
    instr0.x.set = original_set
    s.kill()
```
result:
```
2026-01-09 16:06:07,548 | measureit.sweeps.Sweep1D | INFO | Sweeping x to 5 (a.u.)
Sweep state: SweepState.ERROR
Error message: Parameter operation failed: Couldn't set x to 0.5.
Set calls before failure: 7
SUCCESS: Sweep1D correctly entered ERROR state on set failure
```

### 4. Sweep2D Outer Parameter Set Error

Tests that outer parameter set failures in Sweep2D trigger ERROR state.

```python
from measureit.sweep.progress import SweepState

# Create a Sweep2D
s = Sweep2D(
    [instr0.x, -2, 2, 0.5],      # inner: x from -2 to 2
    [instr0.y, -2, 2, 0.5],      # outer: y from -2 to 2
    inter_delay=0.1,
    outer_delay=0.5,
    save_data=False,
    plot_data=True
)
s.follow_param(instr0.parabola)

# Patch outer parameter set to fail
original_set = instr0.y.set
fail_on_next = [False]

def conditional_failing_set(value):
    if fail_on_next[0]:
        raise Exception("Outer parameter set failed: communication error")
    return original_set(value)

instr0.y.set = conditional_failing_set

try:
    # Start the sweep
    s.start(ramp_to_start=False)

    import time
    time.sleep(1)  # Let first inner sweep complete

    # Enable failure for the next outer parameter set
    fail_on_next[0] = True

    time.sleep(2)  # Wait for outer step and error

    print(f"Sweep state: {s.progressState.state}")
    print(f"Error message: {s.progressState.error_message}")

    if s.progressState.state == SweepState.ERROR:
        print("SUCCESS: Sweep2D correctly entered ERROR state on outer param set failure")
    else:
        print(f"Status: {s.progressState.state}")
finally:
    instr0.y.set = original_set
    s.kill()
```

### 5. SimulSweep Ramping Failure Error

Tests that SimulSweep ramping failures trigger ERROR state with tolerance info.

**Note:** SimulSweep reads parameter values during `__init__`, so set parameters to known positions first.

```python
from measureit.sweep.progress import SweepState
from measureit.tools.util import safe_get

# First, set parameters to known positions BEFORE creating SimulSweep
instr0.x.set(0.0)
instr0.y.set(0.0)

# Create a SimulSweep (reads current param values during init)
params_dict = {
    instr0.x: {"start": 0, "stop": 5, "step": 0.1},
    instr0.y: {"start": 0, "stop": 5, "step": 0.1},
}

s = SimulSweep(
    params_dict,
    inter_delay=0.1,
    save_data=False,
    plot_data=False,  # Disable plotting to avoid side effects
    bidirectional=False
)

# Now set parameters to WRONG positions (simulating a failed ramp)
instr0.x.set(2.5)  # Expected: 0, Actual: 2.5
instr0.y.set(2.5)

print(f"After manual set - x={safe_get(instr0.x)}, y={safe_get(instr0.y)}")

# Simulate ramping state
s.progressState.state = SweepState.RAMPING

# Expected values dictionary (what the ramp should have achieved)
vals_dict = {
    instr0.x: 0.0,
    instr0.y: 0.0,
}

# Call done_ramping - it should detect the position mismatch
s.done_ramping(vals_dict, start_on_finish=False, pd=None)

print(f"Sweep state: {s.progressState.state}")
print(f"Error message: {s.progressState.error_message}")

if s.progressState.state == SweepState.ERROR:
    print("SUCCESS: SimulSweep correctly entered ERROR state on ramping failure")
    print("Error mentions 'err' parameter:", "err=" in s.progressState.error_message)
else:
    print(f"NOTE: State is {s.progressState.state}")
    # Debug: show calculation
    p_step = 0.1
    actual = safe_get(instr0.x)
    expected = 0.0
    position_error = abs(actual - expected) - abs(p_step / 2)
    tolerance = abs(p_step) * s.err
    print(f"  actual={actual}, expected={expected}")
    print(f"  position_error={position_error}, tolerance={tolerance}")
    print(f"  Error should trigger: {position_error > tolerance}")

s.kill()
```

### 6. SweepQueue Error Propagation

Tests that SweepQueue correctly detects and handles sweep errors.

```python
from measureit.sweep.progress import SweepState
from measureit.tools.sweep_queue import SweepQueue
import time

# Create SweepQueue
sq = SweepQueue(inter_delay=0.5)

# Create sweeps
s1 = Sweep1D(
    instr0.x, start=0, stop=2, step=0.5,
    inter_delay=0.1, save_data=False, plot_data=True
)
s1.follow_param(instr0.parabola)

s2 = Sweep1D(
    instr0.y, start=0, stop=2, step=0.5,
    inter_delay=0.1, save_data=False, plot_data=True
)
s2.follow_param(instr0.parabola)

sq.append(s1)
sq.append(s2)

# Patch first sweep to fail mid-way
original_set = instr0.x.set
call_count = [0]

def failing_set(value):
    call_count[0] += 1
    if call_count[0] > 3:
        raise Exception("Parameter error")
    return original_set(value)

instr0.x.set = failing_set

try:
    sq.start(rts=False)

    time.sleep(3)

    print(f"Queue state: {sq.state()}")
    print(f"Current sweep state: {sq.current_sweep.progressState.state if sq.current_sweep else 'None'}")
    print(f"Remaining in queue: {len(sq.queue)}")

    if sq.state() == SweepState.ERROR or (sq.current_sweep and sq.current_sweep.progressState.state == SweepState.ERROR):
        print("SUCCESS: SweepQueue detected error and stopped")
        print(f"Second sweep (s2) still in queue: {s2 in sq.queue}")
    else:
        print(f"Queue status: {sq.state()}")
finally:
    instr0.x.set = original_set
    sq.kill()
```
result:
```
2026-01-09 16:08:25,176 | measureit.sweeps.queue | INFO | Starting sweeps
2026-01-09 16:08:25,177 | measureit.sweeps.queue | INFO | Starting sweep of x from 0 (a.u.) to 2 (a.u.)
2026-01-09 16:08:25,178 | measureit.sweeps.Sweep1D | INFO | Sweeping x to 2 (a.u.)
Queue state: SweepState.ERROR
Current sweep state: SweepState.ERROR
Remaining in queue: 1
SUCCESS: SweepQueue detected error and stopped
Second sweep (s2) still in queue: True
```
---
## Running the Tests

### Option 1: Run in Jupyter Notebook

```python
# Copy and paste the comprehensive test script into a Jupyter cell
# Run the cell to execute all tests
```

### Option 2: Run from Command Line

```bash
source ~/miniforge3/etc/profile.d/conda.sh && conda activate instrMCPdev
cd /Users/caijiaqi/GitHub/MeasureIt
python test_error_comprehensive.py
```

### Option 3: Run Unit Tests

```bash
source ~/miniforge3/etc/profile.d/conda.sh && conda activate instrMCPdev
cd /Users/caijiaqi/GitHub/MeasureIt

# Run all error handling unit tests
python -m pytest tests/unit/test_error_handling.py -v

# Run specific test classes
python -m pytest tests/unit/test_error_handling.py::TestRampingFailureErrorHandling -v
python -m pytest tests/unit/test_error_handling.py::TestSweep2DOuterParamErrorHandling -v
python -m pytest tests/unit/test_error_handling.py::TestM4GErrorHandling -v
```

---

## Expected Results

| Test | Expected Behavior |
|------|-------------------|
| Sweep0D parameter read failure | Transitions to ERROR state, error message set |
| Sweep1D ramping position mismatch | ERROR state, message mentions tolerance |
| SimulSweep ramping failure | ERROR state, message includes `err=` value |
| Sweep2D outer param set failure | ERROR state, message identifies outer param |
| SweepQueue with sweep error | Queue stops, error logged, remaining sweeps preserved |
| mark_error idempotency | Only one completed signal, first error preserved |
| clear_error | State -> READY, error_message -> None, error_count -> 0 |
| Inner sweep error propagation | Outer Sweep2D enters ERROR state |
