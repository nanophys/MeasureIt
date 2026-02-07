# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Identity

MeasureIt is a QCoDeS-based measurement software for condensed matter physics experiments. It is published on PyPI as `qmeasure` but imported as `measureit`. The repository name is `MeasureIt`.

## Build & Development Commands

```bash
# Install (editable with all dev deps)
pip install -e ".[dev,docs,jupyter]"

# Run all tests with coverage
pytest

# Run specific test categories
pytest tests/unit -v
pytest tests/integration -v
pytest tests/e2e -v
pytest -m "not slow"

# Run a single test file
pytest tests/unit/test_sweep1d.py -v

# Lint and format
make format          # ruff format + ruff check --fix
make lint            # ruff format --check + ruff check + mypy

# Build docs
make docs            # outputs to docs/source/_build/html/
```

Tests use `QT_QPA_PLATFORM=offscreen` (set in `tests/conftest.py`). Qt/pytest-qt integration tests are skipped in CI but should be run locally. Each test gets an isolated `MEASUREIT_HOME` via the `temp_measureit_home` fixture.

## Architecture

### Sweep Hierarchy

`BaseSweep` (in `src/measureit/sweep/base_sweep.py`) is the central class. It owns:
- A `RunnerThread` (QThread in `_internal/runner_thread.py`) for data acquisition
- A `Plotter` (QObject in `_internal/plotter_thread.py`) for real-time visualization
- `ProgressState` / `SweepState` for status tracking
- Parameter following, QCoDeS `Measurement` creation, and save/plot lifecycle

Concrete sweep types: `Sweep0D` (time-based), `Sweep1D` (single param), `Sweep2D` (dual param, composes an inner `Sweep1D`), `SimulSweep`, `SweepIPS`, `GateLeakage`, `Sweep1D_listening`.

### Concurrency Guard

A module-level `WeakSet` (`_ACTIVE_SWEEPS`) enforces that only one non-queued sweep runs at a time. Inner sweeps and sweeps sharing a parent chain are considered "related" and allowed. `SweepQueue` bypasses this guard. `start_force()` kills unrelated active sweeps before starting.

### Threading Model

All threading uses PyQt5 `QThread` + signals/slots, **not** Python `threading.Thread`. This is required even in headless/Jupyter usage because the sweep loop (`RunnerThread.run()`) communicates data points back via `pyqtSignal`. The `conftest.py` provides a session-scoped `qapp` fixture and per-test `cleanup_qt_threads` to prevent segfaults.

### Package Layout

```
src/measureit/
    sweep/              # Sweep classes (base_sweep, sweep0d/1d/2d, simul_sweep, etc.)
    _internal/          # RunnerThread, Plotter (not public API)
    tools/              # sweep_queue, util (init_database, safe_get/set), safe_ramp, tracking
    visualization/      # heatmap_thread, helper (pyqtgraph-based)
    legacy/             # Old matplotlib-based plotter/heatmap threads
    Drivers/            # QCoDeS instrument drivers for lab hardware
    config.py           # Data directory resolution (MEASUREIT_HOME / platformdirs)
    logging_utils.py    # Sweep file logging + Jupyter notebook log handler
    _deprecation.py     # FutureWarning shims for old import paths
```

Top-level shim modules (`base_sweep.py`, `sweep0d.py`, etc. at `src/measureit/`) re-export from `sweep/` with deprecation warnings. New code should import from `measureit.sweep.*` or the top-level `measureit` namespace.

### Data Directory

Priority: `set_data_dir()` > `MEASUREIT_HOME` env > legacy `MeasureItHome` env > `platformdirs` default. Subdirectories (`Databases`, `logs`, `cfg`, `Origin Files`) are created lazily on first access via `get_path()`.

### Sweep Timing Constraints

`inter_delay` minimum: 0.01s (10ms). `outer_delay` minimum: 0.1s (100ms). Values below these raise `ValueError`.

## Testing Conventions

- Mock instruments use `qcodes.parameters.Parameter` subclasses (see `conftest.py::mock_parameter`)
- `fast_sweep_kwargs` fixture provides `inter_delay=0.01, save_data=False, plot_data=False, suppress_output=True`
- `conftest.py` auto-clears QCoDeS instrument registry and `_ACTIVE_SWEEPS` between tests
- Pandas is stubbed in `conftest.py` to avoid binary-compat issues in CI

## Code Style

- Ruff (line-length 88, Google docstrings, `py38` target)
- Mypy with strict settings (configured in `pyproject.toml`)
- `*_ui.py` files are auto-generated and excluded from all linting

## Known Issues

- `ipykernel` 7.0.x breaks Qt event loop; pinned to `>=6.29,!=7.*`
- pytest-qt can cause macOS segfaults during teardown; `conftest.py` includes extensive guards
