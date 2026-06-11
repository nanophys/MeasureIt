"""Regression tests: starting a plotting sweep without a QApplication must not
abort the host process.

Bug: in a Jupyter kernel where the user never ran ``%gui qt`` or
``measureit.tools.ensure_qt()``, ``QApplication.instance()`` is ``None``.
``BaseSweep.start()`` (plot_data=True) then constructs ``Plotter`` and calls
``Plotter.create_figs()``, which instantiates ``QWidget()`` with no guard.
Qt emits qFatal "QWidget: Must construct a QApplication before a QWidget",
which calls ``abort()`` and kills the kernel process.

Because the failure mode is a hard C-level abort (SIGABRT), the repro must run
in a *subprocess*: the pytest process itself owns a QApplication (session
``qapp`` fixture) and would otherwise be killed too. The child process mimics
a bare Jupyter kernel: real PyQt5, no QApplication, then ``sweep.start()``.

While the bug exists the child dies on SIGABRT before printing the sentinel,
so the first test FAILS. With the fix, ``BaseSweep.start()`` sets up Qt via
``measureit.tools.ensure_qt_app_for_plotting()`` (creating a QApplication when
the safety probe passes, or disabling plotting with a warning otherwise), so
``start()`` returns normally — the child prints the sentinel and exits 0.

The second test covers the defensive backstop: callers that bypass
``BaseSweep.start()`` and hit ``Plotter.create_figs()`` while Qt cannot be
started must get a catchable ``RuntimeError`` instead of a process abort.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_CHILD_PREAMBLE = """
    import os
    import sys
    import types

    # Mirror tests/conftest.py: stub pandas if the real one is broken/absent.
    try:
        import pandas  # noqa: F401
    except Exception:
        stub = types.ModuleType("pandas")

        class _StubDataFrame:
            def __init__(self, *args, **kwargs):
                pass

            def to_csv(self, *args, **kwargs):
                pass

            def __setitem__(self, key, value):
                pass

        stub.DataFrame = _StubDataFrame
        sys.modules["pandas"] = stub

    from PyQt5.QtWidgets import QApplication

    # Precondition: this process is a stand-in for a Jupyter kernel where the
    # user never ran %gui qt / ensure_qt(), i.e. no QApplication exists yet.
    assert QApplication.instance() is None, "precondition violated: QApplication exists"
"""

CHILD_SCRIPT = textwrap.dedent(
    _CHILD_PREAMBLE
    + """
    from qcodes.parameters import Parameter

    class MockParameter(Parameter):
        def get_raw(self):
            return 0.0

        def set_raw(self, value):
            pass

    from measureit.sweep.sweep0d import Sweep0D

    sweep = Sweep0D(
        max_time=0.05,
        inter_delay=0.01,
        save_data=False,
        plot_data=True,  # the trigger: forces Plotter.create_figs() in start()
        suppress_output=True,
    )
    sweep.follow_param(MockParameter("voltage", unit="V", label="Voltage"))

    try:
        # While the bug exists, Qt aborts the whole process inside start()
        # ("QWidget: Must construct a QApplication before a QWidget") and the
        # sentinel below is never printed. With the fix, start() must return
        # normally (auto-created QApplication, or plotting disabled with a
        # warning) — it must NOT raise.
        sweep.start()
    finally:
        try:
            sweep.kill()
            if sweep.runner is not None:
                sweep.runner.wait(2000)
        except Exception:
            pass

    print("KERNEL_SURVIVED")
    sys.stdout.flush()
    # Skip interpreter/Qt teardown entirely; the verdict has been delivered.
    os._exit(0)
    """
)

BACKSTOP_SCRIPT = textwrap.dedent(
    _CHILD_PREAMBLE
    + """
    # Simulate an environment where Qt cannot start (the probe failed), then
    # call Plotter.create_figs() directly, bypassing BaseSweep.start(). The
    # backstop must raise a catchable RuntimeError, never abort the process.
    import measureit.tools.ipython as mip

    mip._probe_cache = mip._ProbeResult(
        ok=False, returncode=1, stdout="", stderr="simulated probe failure"
    )
    mip._probe_qt_support = lambda timeout=5.0: mip._probe_cache

    from qcodes.parameters import Parameter

    class MockParameter(Parameter):
        def get_raw(self):
            return 0.0

        def set_raw(self, value):
            pass

    from measureit.sweep.sweep0d import Sweep0D
    from measureit._internal.plotter_thread import Plotter

    sweep = Sweep0D(
        max_time=0.05,
        inter_delay=0.01,
        save_data=False,
        plot_data=False,
        suppress_output=True,
    )
    sweep.follow_param(MockParameter("voltage", unit="V", label="Voltage"))

    plotter = Plotter(sweep)
    try:
        plotter.create_figs()
    except RuntimeError as exc:
        assert "QApplication" in str(exc) or "Qt" in str(exc), str(exc)
        print("BACKSTOP_RAISED")
        sys.stdout.flush()
        os._exit(0)

    print("NO_ERROR_RAISED")
    sys.stdout.flush()
    os._exit(1)
    """
)


def _run_child(tmp_path, temp_measureit_home, name, source):
    script = tmp_path / name
    script.write_text(source)

    env = os.environ.copy()
    # The child must use REAL PyQt5 (tests/unit/conftest.py exports
    # MEASUREIT_FAKE_QT=1 into the environment; that would mask the bug).
    env.pop("MEASUREIT_FAKE_QT", None)
    # MEASUREIT_FORCE_NON_PLOTTING silently disables plotting and would also
    # mask the bug; MEASUREIT_FORCE_QT skips the safety probe.
    env.pop("MEASUREIT_FORCE_NON_PLOTTING", None)
    env.pop("MEASUREIT_FORCE_QT", None)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["MEASUREIT_HOME"] = str(temp_measureit_home)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_ROOT / "src"), env.get("PYTHONPATH", "")]
    )

    return subprocess.run(
        [sys.executable, str(script)],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_sweep_start_without_qapplication_does_not_kill_process(
    tmp_path, temp_measureit_home
):
    """sweep.start() with plot_data=True and no QApplication must not abort."""
    result = _run_child(tmp_path, temp_measureit_home, "child_no_qapp.py", CHILD_SCRIPT)

    # Pre-fix: returncode is -SIGABRT (-6) and stderr contains the qFatal
    # message; the sentinel never appears. Post-fix: exit 0 with sentinel.
    assert result.returncode == 0 and "KERNEL_SURVIVED" in result.stdout, (
        "Starting a sweep with plot_data=True and no QApplication killed the "
        "process (this is the Jupyter kernel crash) or raised from start().\n"
        f"returncode={result.returncode}\n"
        f"stdout={result.stdout!r}\n"
        f"stderr={result.stderr!r}"
    )


def test_plotter_create_figs_backstop_raises_instead_of_aborting(
    tmp_path, temp_measureit_home
):
    """Direct Plotter.create_figs() with Qt unavailable raises RuntimeError."""
    result = _run_child(
        tmp_path, temp_measureit_home, "child_backstop.py", BACKSTOP_SCRIPT
    )

    assert result.returncode == 0 and "BACKSTOP_RAISED" in result.stdout, (
        "Plotter.create_figs() without a working Qt must raise a catchable "
        "RuntimeError, not abort the process or proceed silently.\n"
        f"returncode={result.returncode}\n"
        f"stdout={result.stdout!r}\n"
        f"stderr={result.stderr!r}"
    )
