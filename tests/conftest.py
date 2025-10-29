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
