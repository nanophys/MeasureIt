# MeasureIt Package Reorganization Plan (Zero‑Downtime, Per Your Mapping)

This plan organizes MeasureIt into role‑based subpackages while preserving all existing imports (e.g., `import MeasureIt.sweep0d`, `from MeasureIt.sweep_queue import SweepQueue`). It follows your mapping exactly and avoids breaking notebooks. Compatibility “links” (stub modules) will be added at old paths to re‑export moved modules without warnings by default.

## Objectives

- Adopt clear subpackages: sweep, visualization, tools, legacy, _private
- Keep all current imports working indefinitely via stub modules
- Provide new canonical imports (optional) under subpackages
- Add tests that mirror your notebook import block

## Final Layout (exactly as requested)

- sweep:
  - base_sweep.py
  - sweep0d.py
  - sweep1d.py
  - sweep1d_listening.py
  - sweep2d.py
  - simul_sweep.py
  - sweep_ips.py
  - gate_leakage.py
- visualization:
  - heatmap_thread.py
  - helper.py
- legacy:
  - heatmap_thread_matplotlib.py
  - plotter_thread_matplotlib.py
- tools:
  - util.py
  - safe_ramp.py
  - sweep_queue.py
  - tracking.py
- _private (internal only):
  - plotter_thread.py
  - runner_thread.py

## Migration Phases

### Phase 1 — Subpackages (no moves)
Create subpackage directories and `__init__.py` that re‑export from current top‑level modules so new paths work immediately. No files are moved yet.

### Phase 2 — Stable Top‑Level Exports (no moves)
In `MeasureIt/__init__.py`, re‑export the public API to support simple imports:

- from `.sweep.sweep0d` import `Sweep0D`
- from `.sweep.sweep1d` import `Sweep1D`
- from `.sweep.sweep2d` import `Sweep2D`
- from `.sweep.simul_sweep` import `SimulSweep`
- from `.sweep.sweep_ips` import `SweepIPS`
- from `.sweep.gate_leakage` import `GateLeakage`
- from `.tools.sweep_queue` import `SweepQueue, DatabaseEntry`
- from `.tools.util` import `init_database`

Keep `__all__` scoped to supported public names.

### Phase 3 — Move Files + Compatibility Stubs (“links”)
Physically move modules to the new subpackages and create thin stub modules at old paths to re‑export the moved code. No deprecation warnings by default.

Example stub (old top‑level file `MeasureIt/sweep0d.py`):
```python
from .sweep.sweep0d import Sweep0D
__all__ = ["Sweep0D"]
```

Add stubs for all modules that move:

- sweep0d.py, sweep1d.py, sweep1d_listening.py, sweep2d.py, simul_sweep.py, sweep_ips.py, gate_leakage.py
- plotter_thread.py, runner_thread.py → re‑export from `._private.*`
- heatmap_thread.py, helper.py → re‑export from `.visualization.*`
- sweep_queue.py, util.py, safe_ramp.py, tracking.py → re‑export from `.tools.*`
- legacy matplotlib modules → re‑export from `.legacy.*` (or move and keep stubs)

Why stubs? Python requires a real module at the old path for imports like `import MeasureIt.sweep0d` to continue working.

### Phase 4 — Update Internal Imports (MeasureIt-only)
Update internal imports to use the new subpackages so the codebase does not rely on stubs:

- `from MeasureIt.base_sweep import BaseSweep`
  → `from MeasureIt.sweep.base_sweep import BaseSweep`
- `from MeasureIt.plotter_thread import Plotter`
  → `from MeasureIt._private.plotter_thread import Plotter`
- `from MeasureIt.util import …`
  → `from MeasureIt.tools.util import …`

### Phase 5 — Tests (mirror your notebook imports)
Add tests that validate the following continue to work:

```
from MeasureIt.sweep1d import Sweep1D
from MeasureIt.sweep2d import Sweep2D
from MeasureIt.sweep0d import Sweep0D
from MeasureIt.util import init_database
from MeasureIt.tracking import *
from MeasureIt.sweep_queue import SweepQueue, DatabaseEntry
from MeasureIt.simul_sweep import SimulSweep
from MeasureIt.gate_leakage import GateLeakage
```

Driver imports remain unchanged and are tested opportunistically (skipped if the packages are not installed):

```
from qcodes.instrument_drivers.stanford_research.SR830 import SR830
from qcodes.instrument_drivers.stanford_research.SR860 import SR860
from qcodes.instrument_drivers.tektronix.Keithley_2450 import Keithley2450
from qcodes.instrument_drivers.tektronix.Keithley_2400 import Keithley2400
try: import nidaqmx; except: pass
```

### Phase 6 — Documentation
Update README and docs:

- Show the new canonical imports (optional): `from MeasureIt.sweep.sweep1d import Sweep1D`
- Emphasize that old imports still work (due to stubs)
- Include an “Old → New” mapping table (below)

## Old → New Mapping (authoritative)

- base_sweep → sweep.base_sweep
- gate_leakage → sweep.gate_leakage
- heatmap_thread_matplotlib → legacy.heatmap_thread_matplotlib
- heatmap_thread → visualization.heatmap_thread
- helper → visualization.helper
- plotter_thread_matplotlib → legacy.plotter_thread_matplotlib
- plotter_thread → _private.plotter_thread
- runner_thread → _private.runner_thread
- safe_ramp → tools.safe_ramp
- simul_sweep → sweep.simul_sweep
- sweep_ips → sweep.sweep_ips
- sweep_queue → tools.sweep_queue
- sweep0d → sweep.sweep0d
- sweep1d_listening → sweep.sweep1d_listening
- sweep1d → sweep.sweep1d
- sweep2d → sweep.sweep2d
- tracking → tools.tracking
- util → tools.util

## Compatibility Guarantee

- All existing imports like `import MeasureIt.sweep0d` and `from MeasureIt.sweep1d import Sweep1D` continue to work through stubs.
- No deprecation warnings by default to keep notebooks clean. If desired later, warnings can be introduced behind an env var flag.

## Rollout & Rollback

1) Land Phases 1–2 (no moves) and validate tests.
2) Land Phases 3–4 (moves + stubs + internal imports) together.
3) Update docs/tests (Phase 5–6).

Rollback: if an issue appears post‑move, revert the changeset that moved files and added stubs; behavior returns to current state.
