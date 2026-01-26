# GitHub Copilot Instructions for MeasureIt

## Project Overview

MeasureIt (installed as `qmeasure`, imported as `measureit`) is a measurement software package built on top of QCoDeS for condensed matter physics experiments at the University of Washington. It provides sweep-based measurement capabilities with real-time Qt-based plotting and threading.

### Key Technologies
- **Language**: Python 3.8+ (primary support for 3.11-3.13)
- **Core Framework**: QCoDeS for instrument control and data management
- **GUI**: PyQt5 with pyqtgraph for real-time plotting
- **Threading**: Qt-based threading (RunnerThread, PlotterThread)
- **Package Manager**: uv (recommended) or pip
- **Testing**: pytest with pytest-qt for Qt event loop handling

## Architecture

### Core Components

1. **Sweep System** (`src/measureit/sweep/`):
   - `BaseSweep`: Foundation class providing parameter following, measurement creation, and thread management
   - `Sweep0D`: Time-based measurements without parameter sweeping
   - `Sweep1D`: Single parameter sweep measurements
   - `Sweep2D`: Dual parameter sweep measurements
   - `SweepQueue`: Batch experiment execution manager

2. **Driver Layer** (`src/measureit/Drivers/`):
   - Custom instrument drivers interfacing with lab equipment
   - Built on top of QCoDeS instrument base classes

3. **Threading Architecture**:
   - `RunnerThread`: Handles data acquisition in background
   - `PlotterThread`: Manages real-time plot updates
   - Uses Qt signals/slots for thread-safe communication

4. **Data Management**:
   - Integration with QCoDeS for data storage
   - Configurable data directory via `MEASUREIT_HOME` environment variable or `measureit.set_data_dir()`
   - Default locations: `~/.local/share/measureit/` (Linux), `~/Library/Application Support/measureit/` (macOS), `C:\Users\<user>\AppData\Local\measureit\` (Windows)

### Package Structure
```
src/measureit/
    sweep/             # Measurement implementations
    base_sweep.py      # Core sweep functionality  
    sweep_queue.py     # Batch execution
    Drivers/           # Instrument drivers
    GUI/               # PyQt5 interface components
    tools/             # Data utilities and helpers
    util.py            # Utility functions
```

## Development Environment

### Setup
```bash
# Using uv (recommended)
uv pip install -e ".[dev,docs,jupyter]"

# Or using pip
pip install -e ".[dev,docs,jupyter]"

# Install pre-commit hooks
pre-commit install
```

### Tools and Configuration

- **Formatting & Linting**: `ruff` (configured in `pyproject.toml`)
  - Replaces black, isort, and flake8
  - Run: `make format` or `ruff format src/ tests/`
  
- **Type Checking**: `mypy` (configured in `pyproject.toml`)
  - Run: `mypy src/`
  - Not all code is fully typed; add type hints to new code

- **Testing**: `pytest` with `pytest-qt` and `pytest-cov`
  - Run: `make test` or `pytest`
  - With coverage: `pytest --cov=src/measureit --cov-report=html`
  - Qt tests may be flaky in CI; run locally for Qt-specific validation

### Makefile Commands
```bash
make install     # Install dependencies
make format      # Format code with ruff
make lint        # Run all quality checks
make test        # Run tests with coverage
make docs        # Build documentation
make clean       # Clean build artifacts
```

## Code Quality Standards

### Style Guidelines
- Follow PEP 8 with ruff formatting (88 character line length)
- Use Google-style docstrings
- Add type hints to new code (mypy compliance)
- Keep imports sorted (handled automatically by ruff)

### Testing Requirements
- Write tests in `tests/` directory using pytest
- Use `pytest.mark.slow` for slow tests
- Use `pytest.mark.integration` for integration tests
- Mock external dependencies (instruments, hardware) using QCoDeS mock instruments
- Each test run uses isolated temporary database and `MEASUREIT_HOME`
- Qt tests should use `pytest-qt` fixtures (`qtbot`)

### Test Organization
```
tests/
    unit/          # Fast, isolated unit tests
    integration/   # Component interaction tests
    e2e/           # End-to-end workflow tests
    stress/        # Performance tests
```

## Common Patterns

### Creating a Sweep
```python
import measureit
from qcodes import Station

# Set up station
station = Station()
# ... add instruments ...

# Create a 1D sweep
sweep = measureit.Sweep1D(
    set_param=dac.voltage,
    start=0,
    stop=1,
    step=0.01,
    inter_delay=0.1
)

# Follow parameters
sweep.follow_param(dmm.voltage, lockin.x)

# Start measurement
sweep.start()
```

### Thread Safety
- Use Qt signals/slots for cross-thread communication
- Never directly modify GUI elements from background threads
- Use `QMetaObject.invokeMethod` for thread-safe calls if needed

### Data Directory Configuration
```python
import measureit

# Programmatic configuration
measureit.set_data_dir('/custom/path')

# Or use environment variable
# export MEASUREIT_HOME="/path/to/data"
```

## Important Considerations

### Known Issues
- `ipykernel` 7.0.x has event-loop bug preventing Qt/pyqtgraph updates
- Stick to `ipykernel>=6.29,!=7.*` (dependency enforced in pyproject.toml)
- pytest-qt tests are not checked in GitHub Actions CI due to flakiness but can be run locally

### Platform-Specific Dependencies
- Windows: Requires NI DAQmx drivers and NI VISA
- Windows: `multipyvu>=1.2.0` for PPMS integration
- Optional drivers: `nidaqmx`, `zhinst`

### Package Names
- **PyPI package name**: `qmeasure`
- **Import name**: `measureit`
- **Repository name**: MeasureIt
- Always use `import measureit` in code, not `import qmeasure`

## Contributing Guidelines

### Before Making Changes
1. Read `CONTRIBUTING.md` for detailed setup instructions
2. Understand existing code patterns and architecture
3. Run tests locally to ensure baseline passes
4. Create focused, minimal changes

### Pull Request Checklist
1. Run `make format` to format code
2. Run `make lint` to check code quality
3. Run `make test` to verify all tests pass
4. Update documentation if adding features
5. Test with real instruments if possible
6. Write descriptive commit messages

### Commit Message Format
```
Add support for new instrument driver

Fix issue with sweep interruption
- Handle keyboard interrupts gracefully
- Ensure proper cleanup of resources
```

## Documentation

- **Online**: https://measureituw.readthedocs.io/
- **Local build**: `make docs` (output in `docs/source/_build/html/`)
- **API docs**: Use Sphinx with Google-style docstrings
- **Format**: ReStructuredText and Markdown (via myst-parser)

## External Resources

- QCoDeS documentation: https://qcodes.github.io/
- PyQt5 documentation: https://www.riverbankcomputing.com/static/Docs/PyQt5/
- Project repository: https://github.com/nanophys/MeasureIt
- Contributing guide: `CONTRIBUTING.md`
- Bug reports: https://github.com/nanophys/MeasureIt/issues

## Active Users

The package is actively used by condensed matter physics labs at:
- University of Washington (David Cobden's lab, Xiaodong Xu's lab)
- MIT (Pablo Jarillo-Herrero's lab, Long Ju's lab)
