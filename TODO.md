# MeasureIt → measureit Migration TODO

## Overview
Converting MeasureIt to be pip-installable by:
1. Renaming package to lowercase `measureit`
2. Removing GUI components (not used)
3. Creating config system for data directory management (no more manual `MeasureItHome` setup)
4. Using `platformdirs` for OS-appropriate default locations

## Architecture Decisions

### ✅ Keep PyQt5
**PyQt5 MUST stay** - it's fundamental to core functionality:
- `QThread` in `runner_thread.py` for async sweep execution
- `QObject`, `pyqtSignal`, `pyqtSlot` in all sweep classes (BaseSweep, Sweep0D, Sweep1D, Sweep2D)
- `plotter_thread.py` uses QObject for thread-safe plotting coordination
- **~13 core files** use PyQt5 for threading/signaling (not just GUI)

### 🗑️ Remove GUI
The `src/MeasureIt/GUI/` directory can be safely deleted:
- Contains standalone GUI application code
- Not imported by core sweep functionality
- Users primarily use Jupyter notebooks

---

## Main Tasks

### 1. Package Renaming
- [x] Rename `src/MeasureIt/` → `src/measureit/`
- [x] Update all imports: `from MeasureIt` → `from measureit`
- [x] Update imports in:
  - [x] All sweep files (sweep0d.py, sweep1d.py, sweep2d.py, etc.)
  - [x] util.py
  - [x] sweep_queue.py
  - [x] All driver files in `Drivers/`
  - [x] Test files in `tests/`
  - [x] Example notebooks in `examples/`
- [x] Update `pyproject.toml` package name: `name = "measureit"`

### 2. Remove GUI Code
- [x] Delete `src/MeasureIt/GUI/` directory entirely
- [x] Verify no core files import from GUI:
  ```bash
  grep -r "from.*GUI" src/ --include="*.py" --exclude-dir=GUI
  grep -r "import.*GUI" src/ --include="*.py" --exclude-dir=GUI
  ```

### 3. Create Configuration System

#### 3.1 Create `src/measureit/config.py`
- [x] Import `platformdirs` and `pathlib.Path`
- [x] Implement `set_data_dir(path)` function
- [x] Implement `get_path(subdir)` function with:
  - [x] Support for subdirs: `'databases'`, `'logs'`, `'cfg'`, `'origin_files'`
  - [x] Priority order:
    1. Programmatically set path via `set_data_dir()`
    2. `MEASUREIT_HOME` environment variable
    3. `MeasureItHome` environment variable (legacy compatibility)
    4. platformdirs default: `user_data_dir('measureit', 'measureit')`
  - [x] **Lazy directory creation**: only create directories when accessed
  - [x] Return `pathlib.Path` objects
  - [x] Add docstrings with examples

#### 3.2 Expose in `src/measureit/__init__.py`
- [x] Add: `from .config import get_path, set_data_dir`
- [x] Update `__all__` to export these functions
- [x] Users can do: `import measureit; measureit.set_data_dir('/my/data')`

### 4. Replace Hardcoded Paths

#### 4.1 Files with `os.environ['MeasureItHome']` (15 occurrences)
- [x] **util.py** (~6 occurrences):
  - [x] Line 103-104: Config file path → `get_path('cfg') / 'qcodesrc.json'`
  - [x] Line 184: Origin Files → `get_path('origin_files') / db`
  - [x] Line 248-251: Database initialization → `get_path('databases') / db`
  - [x] Line 261-263: Database initialization → `get_path('databases') / db_fn`
  - [x] Line 268: Origin Files → `get_path('origin_files') / exp.name`
  - [x] Add `from .config import get_path` at top

- [x] **sweep_queue.py**:
  - [x] Line 534: Database path → `get_path('databases') / f'{db}.db'`
  - [x] Add `from .config import get_path` at top

- [x] Remove all uses of `os.environ['MeasureItHome']` from:
  - [x] GUI files (being deleted anyway)
  - [x] Example notebooks
  - [x] Tests

#### 4.2 Fix Windows Path Separators
Replace all `\\` with `pathlib.Path` `/` operator:
- [x] util.py: `'\\Databases\\'`, `'\\Origin Files\\'`, `'\\cfg\\'`
- [x] sweep_queue.py: `'\\Databases\\'`
- [x] Any other hardcoded path strings

#### 4.3 Use `pathlib.Path` consistently
- [x] Ensure all path operations use `Path` objects
- [x] Replace `os.path.isfile()` with `Path.is_file()`
- [x] Replace `os.path.isdir()` with `Path.is_dir()`
- [x] Replace `os.path.exists()` with `Path.exists()`
- [x] Replace `os.mkdir()` with `Path.mkdir(parents=True, exist_ok=True)`

### 5. Update Dependencies

#### 5.1 Update `pyproject.toml`
- [x] Change `name = "measureit"` (lowercase)
- [x] Add to dependencies: `"platformdirs>=3.0.0",`
- [x] **Keep** `"PyQt5>=5.15.0",` (required for core functionality)
- [x] Update package find location if needed
- [x] Update tool configurations (pytest, ruff, mypy) to reference `measureit`

### 6. Update Documentation

#### 6.1 Update `README.md`
- [x] Remove "Add MeasureItHome and database" section
- [x] Add new "Installation" section:
  ```markdown
  ## Installation

  ### Using pip (recommended)
  ```bash
  pip install measureit
  ```

  ### From source
  ```bash
  git clone https://github.com/nanophys/MeasureIt.git
  cd MeasureIt
  pip install -e .
  ```
  ```
- [x] Add "Data Directory Configuration" section:
  ```markdown
  ## Data Directory Configuration

  measureit stores databases, logs, and configuration files. You have three options:

  ### Option 1: Use defaults (recommended)
  Data is automatically stored in OS-appropriate locations:
  - **Linux**: `~/.local/share/measureit/`
  - **macOS**: `~/Library/Application Support/measureit/`
  - **Windows**: `C:\Users\<username>\AppData\Local\measureit\`

  ### Option 2: Set environment variable
  ```bash
  export MEASUREIT_HOME="/path/to/your/data"  # Linux/macOS
  set MEASUREIT_HOME="C:\path\to\data"        # Windows
  ```

  ### Option 3: Programmatic configuration
  ```python
  import measureit
  measureit.set_data_dir('/custom/path')
  ```

  ### Migration from old setup
  If you have existing `MeasureItHome` setup:
  - The `MeasureItHome` environment variable still works (backward compatible)
  - Or copy your `databases/` folder to the new location
  ```
- [x] Update all code examples to use `import measureit`
- [x] Remove GUI-related documentation
- [x] Update "Basic Usage" section

#### 6.2 Update `CONTRIBUTING.md`
- [x] Remove MeasureItHome setup instructions (lines 41-47)
- [X] Update package name references to `measureit`

### 7. Update Examples
- [x] Update `examples/content/quick start.ipynb`:
  - [x] Remove `os.environ['MeasureItHome']` usage (lines 37, 434, 474)
  - [x] Update imports to `measureit`
  - [x] Update database path to use `measureit.get_path('databases')`
  - [x] Test notebook runs successfully

### 8. Update Tests
- [x] Update `tests/test_sweep.py` *(obsolete file removed; covered by `test_quickstart_sweeps.py` and related suites)*:
  - [x] Remove commented `sys.path.append(os.environ['MeasureItHome'])` *(N/A)*
  - [x] Remove MeasureItHome usage *(N/A)*
  - [x] Update imports to `measureit` *(N/A)*
  - [x] Update to use `get_path()` for config and databases *(N/A)*

---

## Testing Checklist

### Pre-Installation Testing
- [x] Verify no syntax errors after renaming
- [x] Run linter: `ruff check src/measureit/`
- [x] Run type checker: `mypy src/measureit/` (if configured)

### Installation Testing

#### Test 1: Clean Virtual Environment (Linux/macOS)
```bash
# Create clean environment
python -m venv test_env_unix
source test_env_unix/bin/activate
pip install --upgrade pip

# Install package
pip install -e .

# Verify installation
python -c "import measureit; print(measureit.__version__)"
python -c "import measureit; print(measureit.get_path('databases'))"
```
- [ ] Installation succeeds
- [ ] Package imports successfully
- [ ] `get_path()` returns expected platform path
- [ ] Default directories created on first access

#### Test 2: Clean Virtual Environment (Windows)
```cmd
python -m venv test_env_windows
test_env_windows\Scripts\activate
pip install --upgrade pip
pip install -e .
python -c "import measureit; print(measureit.get_path('databases'))"
```
- [x] Installation succeeds on Windows
- [x] Paths use correct Windows format

#### Test 3: Environment Variable Override
```bash
export MEASUREIT_HOME="/tmp/measureit_test"
python -c "import measureit; print(measureit.get_path('databases'))"
# Should print: /tmp/measureit_test/databases
```
- [x] Environment variable is respected
- [x] Directories created at custom location

#### Test 4: Programmatic Configuration
```python
import measureit
measureit.set_data_dir('/tmp/custom_measureit')
print(measureit.get_path('databases'))
# Should print: /tmp/custom_measureit/databases
```
- [x] Programmatic setting overrides env vars
- [x] Custom path is used

#### Test 5: Legacy Compatibility
```bash
export MeasureItHome="/tmp/legacy_path"
unset MEASUREIT_HOME
python -c "import measureit; print(measureit.get_path('databases'))"
# Should print: /tmp/legacy_path/databases
```
- [x] Legacy `MeasureItHome` env var still works
- [x] Backward compatibility maintained

### Functional Testing

#### Test 6: Run Example Notebook
- [x] Open `examples/content/quick start.ipynb`
- [x] Run all cells
- [x] Verify:
  - [x] Mock instruments initialize
  - [x] Sweeps execute
  - [x] Database file created at `get_path('databases')`
  - [x] Plots display correctly
  - [x] No errors or warnings

#### Test 7: Core Sweep Functionality
```python
import measureit
from measureit import Sweep1D, Sweep0D
from qcodes.instrument_drivers.mock_instruments import MockParabola

# Test basic sweep creation
mock = MockParabola('mock_parabola')
sweep = Sweep1D(mock.x, 0, 10, 0.1)
# Should work without errors
```
- [x] Sweep classes import correctly
- [x] PyQt5 threading works
- [x] No import errors

#### Test 8: Database Creation
```python
import measureit
import qcodes as qc

# Verify database creation
db_path = measureit.get_path('databases') / 'test.db'
qc.initialise_or_create_database_at(str(db_path))
```
- [x] Database directory created
- [x] Database file created successfully
- [x] Path handling works correctly

### Cross-Platform Testing
- [ ] Test on Linux (Ubuntu/Debian)
- [ ] Test on macOS
- [x] Test on Windows 10/11
- [ ] Verify path separators work on all platforms
- [ ] Verify default locations are appropriate per OS

### Dependency Testing
- [x] All required packages install
- [x] PyQt5 threading works
- [x] platformdirs provides correct paths
- [x] qcodes integration works
- [x] matplotlib plotting works

---

## Migration Guide for Existing Users

### For Users with Existing `MeasureItHome` Setup

**Option 1: Keep using environment variable (easiest)**
- Nothing changes! `MeasureItHome` env var still works
- Update package: `pip install --upgrade measureit`

**Option 2: Migrate to new system**
1. Note your current database location: `echo $MeasureItHome`
2. Upgrade package: `pip install --upgrade measureit`
3. Copy data to new location:
   ```bash
   NEW_LOC=$(python -c "import measureit; print(measureit.get_path(''))")
   cp -r $MeasureItHome/databases $NEW_LOC/
   cp -r $MeasureItHome/cfg $NEW_LOC/ 2>/dev/null || true
   ```
4. Remove `MeasureItHome` from your shell config
5. Optionally set `MEASUREIT_HOME` if you want custom location

**Option 3: Use custom location**
- Set `MEASUREIT_HOME` environment variable
- Or use `measureit.set_data_dir()` in your scripts

---

## Post-Installation Verification

### Quick Smoke Test
```python
#!/usr/bin/env python3
"""Quick verification that measureit is installed correctly."""

import sys

def test_import():
    """Test basic import."""
    try:
        import measureit
        print("✓ measureit imports successfully")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_config():
    """Test configuration system."""
    try:
        import measureit
        db_path = measureit.get_path('databases')
        print(f"✓ get_path() works: {db_path}")

        # Test custom path
        measureit.set_data_dir('/tmp/test_measureit')
        custom = measureit.get_path('databases')
        assert str(custom).startswith('/tmp/test_measureit')
        print(f"✓ set_data_dir() works: {custom}")
        return True
    except Exception as e:
        print(f"✗ Config test failed: {e}")
        return False

def test_core_imports():
    """Test core functionality imports."""
    try:
        from measureit import Sweep0D, Sweep1D, Sweep2D
        from measureit import BaseSweep, SweepQueue
        print("✓ Core sweep classes import successfully")
        return True
    except ImportError as e:
        print(f"✗ Core imports failed: {e}")
        return False

def test_pyqt():
    """Test PyQt5 threading works."""
    try:
        from measureit.base_sweep import BaseSweep
        from measureit.runner_thread import RunnerThread
        from PyQt5.QtCore import QObject
        print("✓ PyQt5 integration works")
        return True
    except ImportError as e:
        print(f"✗ PyQt5 test failed: {e}")
        return False

if __name__ == '__main__':
    tests = [
        test_import,
        test_config,
        test_core_imports,
        test_pyqt,
    ]

    results = [t() for t in tests]

    if all(results):
        print("\n✅ All tests passed! measureit is ready to use.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Check installation.")
        sys.exit(1)
```

- [x] Create `tests/verify_install.py` with above content
- [x] Run after installation to verify everything works

---

## Notes & Gotchas

### Important Notes
- **DO NOT remove PyQt5** - it's core infrastructure, not just for GUI
- **Lazy directory creation** - directories only created when first accessed
- **Path objects everywhere** - use `pathlib.Path`, not string concatenation
- **Backward compatible** - old `MeasureItHome` env var still works

### Common Issues & Solutions

**Issue**: Import errors after renaming
- **Solution**: Check all `from MeasureIt` → `from measureit` (case sensitive)

**Issue**: Paths don't work on Windows
- **Solution**: Use `Path` objects, not string concatenation with `/` or `\\`

**Issue**: Directories not created
- **Solution**: They're created lazily on first access, not on import

**Issue**: Can't find database files
- **Solution**: Check `measureit.get_path('databases')` to see where they are

---

## Completion Criteria

Before marking as complete:
- [ ] All main tasks checked off
- [x] All tests pass
- [x] Package installs via `pip install -e .`
- [x] Example notebook runs successfully
- [x] README updated and clear
- [ ] Works on at least 2 platforms (Linux/macOS or Windows)
- [x] No `os.environ['MeasureItHome']` references in core code
- [x] No `\\` path separators (use `Path` instead)
