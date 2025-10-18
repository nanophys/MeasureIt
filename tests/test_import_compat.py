import importlib
import pytest


def test_import_measureit_public_modules():
    # Canonical subpackage imports (no deprecation warnings)
    from measureit.sweep import (
        Sweep0D,
        Sweep1D,
        Sweep2D,
        SimulSweep,
        SweepIPS,
        GateLeakage,
    )
    assert all([Sweep0D, Sweep1D, Sweep2D, SimulSweep, SweepIPS, GateLeakage])
    # Tools
    from measureit.tools import init_database  # noqa: F401
    from measureit.tools.sweep_queue import SweepQueue, DatabaseEntry  # noqa: F401
    import measureit.tools.tracking as _trk  # noqa: F401


def test_import_qcodes_drivers_available():
    # Optional external drivers: skip test if not installed in environment
    pytest.importorskip('qcodes')

    m = pytest.importorskip('qcodes.instrument_drivers.stanford_research.SR830')
    assert hasattr(m, 'SR830')
    m = pytest.importorskip('qcodes.instrument_drivers.stanford_research.SR860')
    assert hasattr(m, 'SR860')
    m = pytest.importorskip('qcodes.instrument_drivers.tektronix.Keithley_2450')
    assert hasattr(m, 'Keithley2450')
    m = pytest.importorskip('qcodes.instrument_drivers.tektronix.Keithley_2400')
    assert hasattr(m, 'Keithley2400')


def test_optional_nidaqmx_import():
    # This package may not be installed; ensure import does not break the suite
    try:
        import nidaqmx  # noqa: F401
    except Exception:
        pytest.skip('nidaqmx not available in this environment')


def test_new_subpackage_paths_work():
    # New canonical imports via subpackages
    from measureit.sweep import (
        Sweep0D,
        Sweep1D,
        Sweep2D,
        SimulSweep,
        SweepIPS,
        GateLeakage,
    )
    assert Sweep0D and Sweep1D and Sweep2D and SimulSweep and SweepIPS and GateLeakage

    # Import tools subpackage minimal exports
    from measureit.tools import init_database, tracking  # noqa: F401
    assert init_database is not None
    # Import SweepQueue from its module to avoid circular import at package init
    from measureit.tools.sweep_queue import SweepQueue, DatabaseEntry  # noqa: F401
    assert SweepQueue and DatabaseEntry

    from measureit.visualization import Heatmap, print_metadata, print_all_metadata  # noqa: F401
    assert Heatmap and print_metadata and print_all_metadata


def test_no_deprecations_with_canonical_imports():
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("error", category=DeprecationWarning)
        # Only subpackage imports should not warn
        from measureit.sweep import Sweep0D, Sweep1D, Sweep2D, SimulSweep, SweepIPS, GateLeakage
        from measureit.tools import init_database, tracking  # noqa: F401
        from measureit.tools.sweep_queue import SweepQueue, DatabaseEntry
        from measureit.visualization import Heatmap  # noqa: F401
        assert all([Sweep0D, Sweep1D, Sweep2D, SimulSweep, SweepIPS, GateLeakage, SweepQueue, DatabaseEntry, init_database])
