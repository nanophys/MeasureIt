# MeasureIt [![Documentation Status](https://readthedocs.org/projects/measureituw/badge/?version=latest)](https://measureituw.readthedocs.io/en/latest/?badge=latest)

Measurement software based on [QCoDeS](https://qcodes.github.io/), developed in University of Washington physics.

## Community information
[Join our slack channel!](https://join.slack.com/t/measureit-workspace/shared_invite/zt-2ws3h3k2q-78XfSUNtqCjSUkydRW2MXA)

## High-Level Design

MeasureIt is a measurement software package built on top of [QCoDeS](https://qcodes.github.io/) for physics experiments. The architecture follows these key patterns:

### Core Architecture
- **Sweep-based Measurement System**: The core abstraction is the `BaseSweep` class with specialized implementations (`Sweep0D`, `Sweep1D`, `Sweep2D`) for different dimensional measurements
- **Qt-based Threading**: Uses PyQt5 with separate threads for data acquisition (`RunnerThread`) and plotting (`PlotterThread`) 
- **Driver Layer**: Custom instrument drivers in the `Drivers/` module that interface with various lab equipment
- **Notebook Workflow**: Designed for Jupyter/CLI usage; PyQt5 powers background threading and signaling
- **Data Management**: Integration with QCoDeS for data storage and experiment management

### Key Components
- **Base Classes**: `BaseSweep` provides the foundation with parameter following, measurement creation, and thread management
- **Measurement Types**: 
  - 0D (time-based measurements)
  - 1D (single parameter sweep) 
  - 2D (dual parameter sweep)
- **Queue System**: `SweepQueue` for batch experiment execution
- **Real-time Plotting**: Live data visualization during measurements
- **Station Management**: QCoDeS Station integration for instrument management

### Package Structure
```
src/measureit/
    sweep/             # Measurement implementations
    base_sweep.py      # Core sweep functionality
    tools/             # Data utilities and sweep helpers
    Drivers/           # Instrument drivers
    visualization/     # Plotting helpers
```

## Quick Start

### Prerequisites

- Python 3.8+
- Git 
- NI DAQmx drivers: http://www.ni.com/en-us/support/downloads/drivers/download/unpackaged.ni-daqmx.291872.html
- NI VISA package: http://www.ni.com/download/ni-visa-18.5/7973/en/

## Installation

  ### Using pip (recommended)
  ```bash
  pip install qmeasure
  ```

  **Note:** The package is installed as `qmeasure`, but you import it as `measureit`:
  ```python
  import measureit  # Import name stays the same
  ```

  ### From source
  ```bash
  git clone https://github.com/nanophys/MeasureIt.git
  cd MeasureIt
  pip install -e .
  ```

## Data Directory Configuration

  MeasureIt (installed as `qmeasure`) stores databases, logs, and configuration files. You have three options:

  ### Option 1: Use defaults 
  Data is automatically stored in OS-appropriate locations:
  - **Linux**: `~/.local/share/measureit/`
  - **macOS**: `~/Library/Application Support/measureit/`
  - **Windows**: `C:\Users\<username>\AppData\Local\measureit\`

  ### Option 2: Set environment variable (recommended)
  ```bash
  export MEASUREIT_HOME="/path/to/your/data"  # Linux/macOS
  set MEASUREIT_HOME="C:\path\to\data"        # Windows
  ```

  ### Option 3: Programmatic configuration
  ```python
  import measureit
  measureit.set_data_dir('/custom/path')
  ```


### Updating MeasureIt (development version)

```bash
cd /path/to/MeasureIt
git pull
pip install -e . --upgrade
```

### Known Issues

- `ipykernel` 7.0.x has a dormant event-loop bug that prevents the Qt/pyqtgraph
  plotter from updating. Stick to `ipykernel>=6.29` (or the newer 7.1+ series).

## Installation & Updating

It is useful to first create a conda environment to manage all the required 
packages for this package to work. First, download some form of conda 
(Miniforge3 is strongly recommended since it comes with mamba):

* Download Miniforge: https://github.com/conda-forge/miniforge
* Download Anaconda: https://www.anaconda.com/download/
* Download Miniconda: https://docs.conda.io/projects/miniconda/en/latest/miniconda-install.html


## Basic Usage

### Programmatic Usage

```python
import measureit
from qcodes import Station

# Create a station and add instruments
station = Station()
# ... add your instruments ...

# Choose where databases should be stored (optional)
measureit.set_data_dir("/path/to/measureit-data")

# Create a 1D sweep
sweep = measureit.Sweep1D(
    set_param=dac.voltage,
    start=0,
    stop=1,
    step=0.01,
    inter_delay=0.1
)

# Follow parameters to measure
sweep.follow_param(dmm.voltage, lockin.x)

# Start the measurement
sweep.start()
```

### Sweep Logging

- All sweeps and the `SweepQueue` now log status messages to timestamped files in
  the MeasureIt data directory's ``logs/`` folder (see *Data Directory
  Configuration* above). Each run creates a file named
  ``sweeps_YYYYMMDD_HHMMSS.log`` that captures info/warning/error messages.
- To mirror those messages inside Jupyter notebooks, attach the notebook handler
  once per kernel:

  ```python
  from measureit import attach_notebook_logging

  attach_notebook_logging()
  ```

  The handler safely marshals log output from background Qt threads back into
  the notebook cell output, so database switches and sweep transitions are
  visible while the queue runs.

## Documentation

### Building Documentation

```bash
# Install documentation dependencies
uv pip install -e ".[docs]"  # or pip install -e ".[docs]"

# Build HTML documentation
cd docs/source
make html
```

The documentation is located in the `docs/source` directory. The built documentation will be in `docs/source/_build/html/`.

### Online Documentation

Visit our [online documentation](https://measureituw.readthedocs.io/en/latest/?badge=latest) for detailed guides and API reference.

## Testing

MeasureIt includes a comprehensive test suite to ensure reliability and correctness.

### Running Tests Locally

```bash
# Install development dependencies
pip install -e ".[dev,jupyter]"

# Run all tests
pytest

# Run with coverage report
pytest --cov=src/measureit --cov-report=html

# Run specific test categories
pytest tests/unit -v           # Unit tests only
pytest tests/integration -v    # Integration tests only
pytest -m "not slow"           # Skip slow tests

# Run tests with Qt debugging
export PYTEST_QT_API=pyqt5
export QT_LOGGING_RULES="*.debug=true"
pytest tests/integration -v -s
```

### Test Organization

- **`tests/unit/`**: Fast, isolated unit tests for individual components
- **`tests/integration/`**: Tests for component interactions (Qt threads, signals)
- **`tests/e2e/`**: End-to-end tests for complete workflows
- **`tests/stress/`**: Performance and stress tests

### Test Infrastructure

MeasureIt uses:
- **pytest** with **pytest-qt** for Qt event loop handling
- **pytest-cov** for coverage reporting
- Mock QCoDeS instruments for hardware-independent testing
- Temporary databases and isolated MEASUREIT_HOME per test

### Continuous Integration

All tests run automatically on:
- Multiple Python versions (3.8-3.12)
- Multiple operating systems (Linux, Windows, macOS)
- Every push and pull request

See [TODO_CI_test_plan.md](TODO_CI_test_plan.md) for detailed testing strategy.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed information about:

- Setting up a development environment
- Code quality standards and tools
- Testing guidelines
- Documentation standards
- Submitting pull requests

For quick development setup:
```bash
# Clone and set up development environment
git clone https://github.com/nanophys/MeasureIt
cd MeasureIt
uv pip install -e ".[dev,docs,jupyter]"  # or pip install -e ".[dev,docs,jupyter]"

# Run tests to verify setup
pytest tests/unit -v
```

## External links and active known users

# Seattle
[David Cobden's lab](https://sites.google.com/uw.edu/nanodevice-physics)

[Xiaodong Xu's lab](https://sites.google.com/uw.edu/xulab)

# Cambridge
[Pablo Jarillo-Herrero's lab](https://jarillo-herrero.mit.edu)

[Long Ju's lab](https://physics.mit.edu/faculty/long-ju)
