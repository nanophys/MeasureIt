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
- [ ] Rename `src/MeasureIt/` → `src/measureit/`
- [ ] Update all imports: `from MeasureIt` → `from measureit`
- [ ] Update imports in:
  - [ ] All sweep files (sweep0d.py, sweep1d.py, sweep2d.py, etc.)
  - [ ] util.py
  - [ ] sweep_queue.py
  - [ ] All driver files in `Drivers/`
  - [ ] Test files in `tests/`
  - [ ] Example notebooks in `examples/`
- [ ] Update `pyproject.toml` package name: `name = "measureit"`

### 2. Remove GUI Code
- [ ] Delete `src/MeasureIt/GUI/` directory entirely
- [ ] Verify no core files import from GUI:
  ```bash
  grep -r "from.*GUI" src/ --include="*.py" --exclude-dir=GUI
  grep -r "import.*GUI" src/ --include="*.py" --exclude-dir=GUI
  ```

### 3. Create Configuration System

#### 3.1 Create `src/measureit/config.py`
- [ ] Import `platformdirs` and `pathlib.Path`
- [ ] Implement `set_data_dir(path)` function
- [ ] Implement `get_path(subdir)` function with:
  - [ ] Support for subdirs: `'databases'`, `'logs'`, `'cfg'`, `'origin_files'`
  - [ ] Priority order:
    1. Programmatically set path via `set_data_dir()`
    2. `MEASUREIT_HOME` environment variable
    3. `MeasureItHome` environment variable (legacy compatibility)
    4. platformdirs default: `user_data_dir('measureit', 'measureit')`
  - [ ] **Lazy directory creation**: only create directories when accessed
  - [ ] Return `pathlib.Path` objects
  - [ ] Add docstrings with examples

#### 3.2 Expose in `src/measureit/__init__.py`
- [ ] Add: `from .config import get_path, set_data_dir`
- [ ] Update `__all__` to export these functions
- [ ] Users can do: `import measureit; measureit.set_data_dir('/my/data')`

### 4. Replace Hardcoded Paths

#### 4.1 Files with `os.environ['MeasureItHome']` (15 occurrences)
- [ ] **util.py** (~6 occurrences):
  - [ ] Line 103-104: Config file path → `get_path('cfg') / 'qcodesrc.json'`
  - [ ] Line 184: Origin Files → `get_path('origin_files') / db`
  - [ ] Line 248-251: Database initialization → `get_path('databases') / db`
  - [ ] Line 261-263: Database initialization → `get_path('databases') / db_fn`
  - [ ] Line 268: Origin Files → `get_path('origin_files') / exp.name`
  - [ ] Add `from .config import get_path` at top

- [ ] **sweep_queue.py**:
  - [ ] Line 534: Database path → `get_path('databases') / f'{db}.db'`
  - [ ] Add `from .config import get_path` at top

- [ ] Remove all uses of `os.environ['MeasureItHome']` from:
  - [ ] GUI files (being deleted anyway)
  - [ ] Example notebooks
  - [ ] Tests

#### 4.2 Fix Windows Path Separators
Replace all `\\` with `pathlib.Path` `/` operator:
- [ ] util.py: `'\\Databases\\'`, `'\\Origin Files\\'`, `'\\cfg\\'`
- [ ] sweep_queue.py: `'\\Databases\\'`
- [ ] Any other hardcoded path strings

#### 4.3 Use `pathlib.Path` consistently
- [ ] Ensure all path operations use `Path` objects
- [ ] Replace `os.path.isfile()` with `Path.is_file()`
- [ ] Replace `os.path.isdir()` with `Path.is_dir()`
- [ ] Replace `os.path.exists()` with `Path.exists()`
- [ ] Replace `os.mkdir()` with `Path.mkdir(parents=True, exist_ok=True)`

### 5. Update Dependencies

#### 5.1 Update `pyproject.toml`
- [ ] Change `name = "measureit"` (lowercase)
- [ ] Add to dependencies: `"platformdirs>=3.0.0",`
- [ ] **Keep** `"PyQt5>=5.15.0",` (required for core functionality)
- [ ] Update package find location if needed
- [ ] Update tool configurations (pytest, ruff, mypy) to reference `measureit`

### 6. Update Documentation

#### 6.1 Update `README.md`
- [ ] Remove "Add MeasureItHome and database" section
- [ ] Add new "Installation" section:
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
- [ ] Add "Data Directory Configuration" section:
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
- [ ] Update all code examples to use `import measureit`
- [ ] Remove GUI-related documentation
- [ ] Update "Basic Usage" section

#### 6.2 Update `CONTRIBUTING.md`
- [ ] Remove MeasureItHome setup instructions (lines 41-47)
- [ ] Update package name references to `measureit`

### 7. Update Examples
- [ ] Update `examples/content/quick start.ipynb`:
  - [ ] Remove `os.environ['MeasureItHome']` usage (lines 37, 434, 474)
  - [ ] Update imports to `measureit`
  - [ ] Update database path to use `measureit.get_path('databases')`
  - [ ] Test notebook runs successfully

### 8. Update Tests
- [ ] Update `tests/test_sweep.py`:
  - [ ] Remove commented `sys.path.append(os.environ['MeasureItHome'])` (line 9)
  - [ ] Remove MeasureItHome usage (lines 81-82)
  - [ ] Update imports to `measureit`
  - [ ] Update to use `get_path()` for config and databases

---

## Testing Checklist

### Pre-Installation Testing
- [ ] Verify no syntax errors after renaming
- [ ] Run linter: `ruff check src/measureit/`
- [ ] Run type checker: `mypy src/measureit/` (if configured)

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
- [ ] Installation succeeds on Windows
- [ ] Paths use correct Windows format

#### Test 3: Environment Variable Override
```bash
export MEASUREIT_HOME="/tmp/measureit_test"
python -c "import measureit; print(measureit.get_path('databases'))"
# Should print: /tmp/measureit_test/databases
```
- [ ] Environment variable is respected
- [ ] Directories created at custom location

#### Test 4: Programmatic Configuration
```python
import measureit
measureit.set_data_dir('/tmp/custom_measureit')
print(measureit.get_path('databases'))
# Should print: /tmp/custom_measureit/databases
```
- [ ] Programmatic setting overrides env vars
- [ ] Custom path is used

#### Test 5: Legacy Compatibility
```bash
export MeasureItHome="/tmp/legacy_path"
unset MEASUREIT_HOME
python -c "import measureit; print(measureit.get_path('databases'))"
# Should print: /tmp/legacy_path/databases
```
- [ ] Legacy `MeasureItHome` env var still works
- [ ] Backward compatibility maintained

### Functional Testing

#### Test 6: Run Example Notebook
- [ ] Open `examples/content/quick start.ipynb`
- [ ] Run all cells
- [ ] Verify:
  - [ ] Mock instruments initialize
  - [ ] Sweeps execute
  - [ ] Database file created at `get_path('databases')`
  - [ ] Plots display correctly
  - [ ] No errors or warnings

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
- [ ] Sweep classes import correctly
- [ ] PyQt5 threading works
- [ ] No import errors

#### Test 8: Database Creation
```python
import measureit
import qcodes as qc

# Verify database creation
db_path = measureit.get_path('databases') / 'test.db'
qc.initialise_or_create_database_at(str(db_path))
```
- [ ] Database directory created
- [ ] Database file created successfully
- [ ] Path handling works correctly

### Cross-Platform Testing
- [ ] Test on Linux (Ubuntu/Debian)
- [ ] Test on macOS
- [ ] Test on Windows 10/11
- [ ] Verify path separators work on all platforms
- [ ] Verify default locations are appropriate per OS

### Dependency Testing
- [ ] All required packages install
- [ ] PyQt5 threading works
- [ ] platformdirs provides correct paths
- [ ] qcodes integration works
- [ ] matplotlib plotting works

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

- [ ] Create `tests/verify_install.py` with above content
- [ ] Run after installation to verify everything works

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
- [ ] All tests pass
- [ ] Package installs via `pip install -e .`
- [ ] Example notebook runs successfully
- [ ] README updated and clear
- [ ] Works on at least 2 platforms (Linux/macOS or Windows)
- [ ] No `os.environ['MeasureItHome']` references in core code
- [ ] No `\\` path separators (use `Path` instead)
