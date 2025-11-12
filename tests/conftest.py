import os
import shutil
import sys
import tempfile
import types
from pathlib import Path

import pytest

# Provide a lightweight stub for pandas to avoid binary-compat issues in CI/dev envs
if "pandas" not in sys.modules:
    pandas_stub = types.ModuleType("pandas")

    class _StubDataFrame:  # minimal stub used only if code paths touch save_to_csv
        def __init__(self, *args, **kwargs):
            pass

        def to_csv(self, *args, **kwargs):
            pass

        def __setitem__(self, key, value):
            pass

    pandas_stub.DataFrame = _StubDataFrame
    sys.modules["pandas"] = pandas_stub


@pytest.fixture(scope="session", autouse=True)
def add_src_to_path():
    """Ensure `src` is on sys.path so `import measureit` works without install."""
    repo_root = Path(__file__).resolve().parents[1]
    src = repo_root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    yield


@pytest.fixture(scope="function")
def temp_measureit_home(monkeypatch):
    """Provide a temporary MEASUREIT_HOME with Databases subfolder."""
    tmpdir = Path(tempfile.mkdtemp(prefix="measureit_home_"))
    (tmpdir / "Databases").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MEASUREIT_HOME", str(tmpdir))
    monkeypatch.delenv("MeasureItHome", raising=False)
    try:
        yield tmpdir
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def quiet_test_env():
    """Reduce noisy logs/warnings during tests without affecting runtime behavior."""
    import warnings

    # General warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
    warnings.filterwarnings("ignore", category=ResourceWarning)
    # Common noisy sources
    warnings.filterwarnings("ignore", category=UserWarning, module=r"pyqtgraph")
    warnings.filterwarnings("ignore", message=r".*PyQt5.*sip.*")

    # Qt / macOS noise suppression via environment (best-effort)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("OS_ACTIVITY_MODE", "disable")  # macOS launchd spam
    os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false;qt.qpa.*=false")
    # Matplotlib backend (should not be used, but avoid backend warnings if imported)
    os.environ.setdefault("MPLBACKEND", "Agg")

    # Disable tqdm monitor thread to prevent macOS segfault during cleanup
    # This must be done before tqdm is imported anywhere
    try:
        import tqdm

        tqdm.tqdm.monitor_interval = 0
    except Exception:
        pass

    # Tame QCoDeS console logging
    try:
        import qcodes as qc

        qc.config.logger.console_level = "CRITICAL"
    except Exception:
        pass


@pytest.fixture(scope="function")
def fast_sweep_kwargs():
    """Common kwargs to create fast, headless sweeps for tests."""
    return dict(
        inter_delay=0.01,
        save_data=False,
        plot_data=False,
        suppress_output=True,
    )


@pytest.fixture(autouse=True, scope="function")
def close_qcodes_instruments_between_tests():
    """Ensure QCoDeS instrument registry is clean between tests.

    Prevents KeyError: 'Another instrument has the name: <name>' when tests
    create mock instruments with the same names across functions.
    """
    # Best effort pre-clean in case a prior test failed mid-way
    try:
        import qcodes as qc

        qc.Instrument.close_all()
    except Exception:
        pass
    try:
        yield
    finally:
        try:
            import qcodes as qc

            qc.Instrument.close_all()
        except Exception:
            pass


@pytest.fixture(scope="session")
def qapp():
    """Create a shared QApplication with safe teardown guards for macOS CI."""
    import sys
    import sip
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication

    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    # Prevent PyQt from destroying QObject instances during interpreter shutdown.
    try:
        sip.setdestroyonexit(False)
    except AttributeError:
        pass

    app = QApplication.instance()
    if app is None:
        argv = sys.argv if sys.argv else []
        app = QApplication(argv)

    yield app


@pytest.fixture
def mock_parameter():
    """Factory fixture to create mock QCoDeS parameters."""
    from qcodes.parameters import Parameter

    class MockParameter(Parameter):
        def __init__(self, name: str, initial_value: float = 0.0, **kwargs):
            super().__init__(name=name, **kwargs)
            self._value = initial_value

        def get_raw(self) -> float:
            return self._value

        def set_raw(self, value: float) -> None:
            self._value = value

    return MockParameter


@pytest.fixture
def mock_parameters(mock_parameter):
    """Create a set of common mock parameters for testing."""
    return {
        "voltage": mock_parameter("voltage", initial_value=0.0, unit="V", label="Voltage"),
        "current": mock_parameter("current", initial_value=0.0, unit="A", label="Current"),
        "temperature": mock_parameter("temperature", initial_value=300.0, unit="K", label="Temperature"),
        "x": mock_parameter("x", initial_value=0.0, unit="V", label="X"),
        "y": mock_parameter("y", initial_value=0.0, unit="V", label="Y"),
        "gate": mock_parameter("gate", initial_value=0.0, unit="V", label="Gate"),
        "freq": mock_parameter("freq", initial_value=1000.0, unit="Hz", label="Frequency"),
    }


@pytest.fixture
def mock_station(mock_parameters):
    """Create a QCoDeS Station with mock instruments."""
    from qcodes import Station

    station = Station()

    # Create mock instrument container
    class MockInstrument:
        def __init__(self, name: str, **parameters):
            self.name = name
            for param_name, param in parameters.items():
                setattr(self, param_name, param)

    # Mock SR830 lock-in amplifier
    sr830 = MockInstrument(
        "SR830",
        x=mock_parameters["x"],
        y=mock_parameters["y"],
        freq=mock_parameters["freq"],
    )

    # Mock Keithley voltage source
    keithley = MockInstrument(
        "Keithley",
        voltage=mock_parameters["voltage"],
        current=mock_parameters["current"],
    )

    station.add_component(sr830)
    station.add_component(keithley)

    yield station

    # Cleanup
    try:
        station.close_all_registered_instruments()
    except Exception:
        pass


@pytest.fixture
def temp_database(temp_measureit_home):
    """Create a temporary QCoDeS database for testing."""
    import qcodes as qc

    db_path = temp_measureit_home / "test.db"
    qc.initialise_or_create_database_at(str(db_path))

    yield db_path


@pytest.fixture
def temp_logs(temp_measureit_home):
    """Provide path to temporary logs directory."""
    logs_dir = temp_measureit_home / "logs"
    logs_dir.mkdir(exist_ok=True)
    return logs_dir


@pytest.fixture
def qt_wait_time():
    """Default wait time for Qt signals in milliseconds."""
    return 5000


@pytest.fixture
def sample_metadata():
    """Provide sample metadata for testing."""
    return {
        "experiment": "test_experiment",
        "sample": "test_sample",
        "user": "test_user",
        "notes": "Test sweep for CI",
    }


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "gui: mark test as requiring GUI components"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "stress: mark test as stress/performance test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )


def pytest_sessionfinish(session, exitstatus):
    """Clean up QApplication before pytest exits to prevent macOS segfault.

    NOTE: There is a known PyQt5 cleanup issue on macOS that causes a bus error/
    segfault AFTER all tests complete successfully. This happens during pytest's
    cleanup phase and does not affect test results. The crash occurs at 100% completion
    and all tests PASS. This issue does not occur on Linux (CI environment).

    Attempts to work around this with os._exit() don't work because the crash occurs
    during the test loop, before pytest_sessionfinish is called.
    """
    import os
    import sys

    try:
        from PyQt5.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.closeAllWindows()
            app.processEvents()

        # Force exit on macOS to bypass PyQt5 cleanup crash
        # Note: This may not always work as crash can occur before this hook
        if sys.platform == "darwin" and exitstatus == 0:
            os._exit(0)
    except Exception:
        if sys.platform == "darwin" and exitstatus == 0:
            os._exit(0)
