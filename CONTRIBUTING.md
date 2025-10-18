# Contributing to measureit

Thank you for your interest in contributing to measureit! This guide will help you set up your development environment and understand our development workflow.

## Development Setup

### Prerequisites

- Python 3.8+
- Git
- NI DAQmx drivers: http://www.ni.com/en-us/support/downloads/drivers/download/unpackaged.ni-daqmx.291872.html
- NI VISA package: http://www.ni.com/download/ni-visa-18.5/7973/en/

### Quick Start with uv (Recommended)

We use `uv` (fast Python package manager) and `ruff` (fast Python linter and formatter) for the best development experience:

1. **Install uv**:
   ```bash
   # On macOS and Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # On Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   
   # Or with pip
   pip install uv
   ```

2. **Clone and install**:
   ```bash
   git clone https://github.com/nanophys/MeasureIt
   cd MeasureIt
   
   # Install with development dependencies
   uv pip install -e ".[dev,docs,jupyter]"
   ```

3. **(Optional) Choose a custom data directory**:

   measureit automatically stores databases, logs, configuration files, and exports in a per-user data directory based on your OS. Override this location in your notebooks or scripts when you need a shared or versioned path:

   ```python
   import measureit
   measureit.set_data_dir("/path/to/measureit-data")
   ```

4. **Set up pre-commit hooks**:
   ```bash
   pre-commit install
   ```

### Alternative Setup Methods

#### Using pip
```bash
git clone https://github.com/nanophys/MeasureIt
cd MeasureIt
pip install -e ".[dev,docs,jupyter]"
pre-commit install
```

#### Using conda (Legacy)
```bash
conda create -n measureit python=3.9
conda activate measureit
git clone https://github.com/nanophys/MeasureIt
cd MeasureIt
pip install -e ".[dev,docs,jupyter]"
```

## Development Workflow

### Using Make Commands (Recommended)

We provide a Makefile with convenient commands for common development tasks:

```bash
# Install development dependencies
make install

# Code quality
make format         # Format and fix code with ruff
make lint           # Check code quality (format + lint + type check)

# Testing
make test           # Run tests with coverage

# Documentation
make docs           # Build documentation

# Maintenance
make clean          # Clean build artifacts

# See all commands
make help
```

### Using Tools Directly

Alternatively, you can run tools directly:

```bash
# Format code with ruff
ruff format src/ tests/

# Lint and fix with ruff
ruff check --fix src/ tests/

# Type check with mypy
mypy src/

# Run tests
pytest

# Run tests with coverage
pytest --cov=src/measureit --cov-report=html --cov-report=term-missing
```

## Code Quality Standards

### Formatting and Linting

We use `ruff` for both code formatting and linting. Ruff replaces multiple tools:
- **Formatting**: Replaces `black`
- **Import sorting**: Replaces `isort`
- **Linting**: Replaces `flake8` and includes many additional checks

Configuration is in `pyproject.toml` under `[tool.ruff]`.

### Type Checking

We use `mypy` for static type checking. While not all code is currently typed, we encourage adding type hints to new code.

### Pre-commit Hooks

Pre-commit hooks automatically run code quality checks before each commit:
- Trailing whitespace removal
- End-of-file fixing
- YAML validation
- Ruff formatting and linting
- MyPy type checking

## Testing

### Running Tests

```bash
# Run all tests
make test

# Run tests with coverage
make test-cov

# Run specific test file
pytest tests/test_specific.py

# Run tests with specific markers (when configured)
pytest -m "not slow"
```

### Writing Tests

- Place tests in the `tests/` directory
- Use descriptive test names starting with `test_`
- Use pytest fixtures for common setup
- Mock external dependencies (instruments, hardware)
- Test both success and failure cases

Example test structure:
```python
import pytest
from measureit import Sweep1D

def test_sweep1d_creation():
    """Test that Sweep1D can be created with valid parameters."""
    # Test implementation here
    pass

def test_sweep1d_invalid_parameters():
    """Test that Sweep1D raises appropriate errors for invalid parameters."""
    with pytest.raises(ValueError):
        # Test implementation here
        pass
```

## Documentation

### Building Documentation

```bash
# Install documentation dependencies
uv pip install -e ".[docs]"

# Build HTML documentation
make docs

# Clean documentation build
make docs-clean
```

The documentation is built using Sphinx and located in `docs/source/`. The built documentation will be in `docs/source/_build/html/`.

### Writing Documentation

- Use Google-style docstrings for functions and classes
- Include examples in docstrings when helpful
- Update relevant documentation when adding features
- Keep the README focused on installation and basic usage

Example docstring:
```python
def follow_param(self, *params: Parameter) -> None:
    """Add QCoDeS parameters to be tracked during measurement.
    
    Args:
        *params: Variable number of QCoDeS Parameter objects to track
        
    Raises:
        ParameterException: If parameter is already being followed
        
    Example:
        >>> sweep = Sweep1D(dac.voltage, 0, 1, 0.1)
        >>> sweep.follow_param(dmm.voltage, lockin.x)
    """
```

## Project Structure

```
MeasureIt/
├── src/measureit/           # Main package source
│   ├── sweep0d.py          # 0D measurements (time-based)
│   ├── sweep1d.py          # 1D parameter sweeps
│   ├── sweep2d.py          # 2D parameter sweeps
│   ├── base_sweep.py       # Core sweep functionality
│   ├── sweep_queue.py      # Batch experiment management
│   ├── GUI/                # PyQt5 user interface
│   ├── Drivers/            # Instrument drivers
│   └── util.py             # Utility functions
├── tests/                  # Test suite
├── docs/                   # Documentation
├── scripts/                # Utility scripts
├── pyproject.toml          # Project configuration
├── Makefile               # Development commands
└── CONTRIBUTING.md        # This file
```

## Submitting Changes

### Before Submitting

1. **Run quality checks**: `make quality-fix`
2. **Run tests**: `make test`
3. **Update documentation** if needed
4. **Test your changes** with real instruments if possible

### Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Run quality checks and tests
5. Commit with descriptive messages
6. Push to your fork
7. Create a pull request

### Commit Message Guidelines

- Use clear, descriptive commit messages
- Start with a verb in present tense
- Keep the first line under 50 characters
- Include more details in the body if needed

Examples:
```
Add support for new instrument driver

Fix issue with sweep interruption
- Handle keyboard interrupts gracefully
- Ensure proper cleanup of resources

Update documentation for new features
```

## Migration from Legacy Setup

If you're migrating from the old conda + black/isort/flake8 setup:

```bash
# Use the migration script
make migrate

# Or manually
uv pip install -e ".[dev,docs,jupyter]"
pre-commit install
```

## Getting Help

- **Issues**: Report bugs and request features on GitHub Issues
- **Discussions**: Use GitHub Discussions for questions
- **Slack**: Join our [Slack channel](https://join.slack.com/t/measureit-workspace/shared_invite/zt-2ws3h3k2q-78XfSUNtqCjSUkydRW2MXA)

## Code of Conduct

Please be respectful and professional in all interactions. We're all here to advance scientific research and help each other succeed. 
