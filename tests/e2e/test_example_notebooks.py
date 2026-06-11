"""End-to-end tests that execute the example notebooks in a real Jupyter kernel.

``examples/content/quick start.ipynb`` is the canonical user workflow: it
creates mock instruments and runs every sweep type. It is executed twice:

1. As written. The first cell calls ``ensure_qt()``, so this validates the
   documented happy path end-to-end.
2. With every ``ensure_qt()`` call stripped. This is the kernel-crash bug
   report verbatim ("When a sweep starts without %gui qt or ensure_qt() run
   before, the Ipython kernel for jupyter lab will crash"): while the bug
   existed, the first ``s.start()`` aborted the kernel with a Qt qFatal; with
   the fix, ``start()`` sets up Qt automatically and the kernel survives.

The notebook was written for human pacing (e.g. ``load_by_id(1)`` immediately
after starting a background sweep), so cells are executed with
``allow_errors=True`` and the assertions target what must always hold:

1. the kernel survives every cell (``DeadKernelError`` fails the test),
2. the import cell succeeds (guards against running in the wrong kernel env),
3. no ``*.start()`` cell raises,
4. no output anywhere contains Qt's fatal "Must construct a QApplication".

The other example notebooks are not executed: ``data processing.ipynb``
requires pre-existing example databases and an instrMCP install, and the
remaining notebooks contain no runnable code.
"""

import json
import os
from pathlib import Path

import pytest

nbformat = pytest.importorskip("nbformat")
nbclient = pytest.importorskip("nbclient")
pytest.importorskip("ipykernel")

from nbclient.exceptions import DeadKernelError  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
QUICK_START = REPO_ROOT / "examples" / "content" / "quick start.ipynb"

# Injected as a final cell so background sweeps/queues are stopped before the
# kernel is asked to shut down (the notebook itself leaves the last SweepQueue
# running, which would otherwise race kernel teardown).
CLEANUP_CELL = """\
# Injected by tests/e2e/test_example_notebooks.py: stop background sweeps so
# kernel shutdown is clean.
import time

try:
    sq.kill()
except Exception:
    pass

from measureit.sweep.base_sweep import _ACTIVE_SWEEPS

for _sweep in list(_ACTIVE_SWEEPS):
    try:
        _sweep.kill()
    except Exception:
        pass

for _sweep in list(_ACTIVE_SWEEPS):
    runner = getattr(_sweep, "runner", None)
    if runner is not None:
        try:
            runner.wait(5000)
        except Exception:
            pass

time.sleep(0.5)
print("CLEANUP_DONE")
"""


def _cell_errors(cell):
    """Return the list of error outputs of a code cell."""
    return [out for out in cell.get("outputs", []) if out.get("output_type") == "error"]


def _format_error(cell, errors):
    src = "".join(cell["source"])
    tracebacks = "\n".join("\n".join(err.get("traceback", [])) for err in errors)
    return f"--- cell ---\n{src}\n--- error ---\n{tracebacks}"


def _strip_ensure_qt(nb):
    """Remove every ``ensure_qt()`` call line from the notebook's code cells.

    This recreates the bug-report scenario: a user runs the sweeps without
    ever enabling Qt first.
    """
    stripped = 0
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        lines = cell["source"].splitlines()
        kept = [ln for ln in lines if not ln.strip().startswith("ensure_qt(")]
        if len(kept) != len(lines):
            stripped += len(lines) - len(kept)
            cell["source"] = "\n".join(kept)
    assert stripped > 0, "expected the notebook to contain ensure_qt() calls"


def _execute_and_check_notebook(nb, tmp_path, temp_measureit_home, monkeypatch):
    """Execute a notebook in a fresh ipykernel and apply the shared checks."""
    # The kernel inherits this process's environment. Make sure it sees real
    # PyQt5 (fake-Qt stubs and FORCE_* shortcuts would mask the crash path),
    # renders offscreen, and writes data into an isolated home.
    monkeypatch.delenv("MEASUREIT_FAKE_QT", raising=False)
    monkeypatch.delenv("MEASUREIT_FORCE_NON_PLOTTING", raising=False)
    monkeypatch.delenv("MEASUREIT_FORCE_QT", raising=False)
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("MPLBACKEND", "Agg")
    monkeypatch.setenv("MEASUREIT_HOME", str(temp_measureit_home))
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join([str(REPO_ROOT / "src"), os.environ.get("PYTHONPATH", "")]),
    )

    nb.cells.append(nbformat.v4.new_code_cell(CLEANUP_CELL))

    client = nbclient.NotebookClient(
        nb,
        kernel_name="python3",
        timeout=180,  # per cell
        startup_timeout=120,
        allow_errors=True,
        resources={"metadata": {"path": str(tmp_path)}},
    )

    try:
        client.execute()
    except DeadKernelError as exc:
        pytest.fail(
            "The kernel DIED while executing the quick start notebook "
            f"(this is the Jupyter kernel crash): {exc}"
        )

    code_cells = [c for c in nb.cells if c.cell_type == "code"]

    # The import cell must succeed, otherwise every later assertion is
    # meaningless (e.g. the kernelspec resolved to an env without measureit).
    import_errors = _cell_errors(code_cells[0])
    assert not import_errors, (
        "The notebook's import cell failed — the kernel is probably not "
        "running in the test environment.\n"
        + _format_error(code_cells[0], import_errors)
    )

    # No sweep/queue start may raise: pre-fix the first bare `s.start()`
    # (which runs before any ensure_qt() in the notebook) aborted the kernel.
    start_failures = []
    for cell in code_cells:
        if ".start(" not in "".join(cell["source"]):
            continue
        errors = _cell_errors(cell)
        if errors:
            start_failures.append(_format_error(cell, errors))
    assert not start_failures, (
        "Sweep start cell(s) raised during notebook execution:\n\n"
        + "\n\n".join(start_failures)
    )

    # Qt's qFatal message must not appear anywhere (it would mean a widget
    # was created without a QApplication somewhere along the way).
    assert "Must construct a QApplication" not in json.dumps(nb), (
        "Qt reported 'Must construct a QApplication before a QWidget' while "
        "running the notebook."
    )

    # The injected cleanup cell ran to completion.
    cleanup_out = json.dumps(code_cells[-1].get("outputs", []))
    assert "CLEANUP_DONE" in cleanup_out, (
        "Injected cleanup cell did not finish:\n"
        + _format_error(code_cells[-1], _cell_errors(code_cells[-1]))
    )


@pytest.mark.slow
def test_quick_start_notebook_executes_without_killing_kernel(
    tmp_path, temp_measureit_home, monkeypatch
):
    """Run quick start.ipynb as written, start-to-finish, in a fresh kernel."""
    nb = nbformat.read(QUICK_START, as_version=4)
    _execute_and_check_notebook(nb, tmp_path, temp_measureit_home, monkeypatch)


@pytest.mark.slow
def test_quick_start_notebook_without_ensure_qt_survives(
    tmp_path, temp_measureit_home, monkeypatch
):
    """Run quick start.ipynb with all ensure_qt() calls removed.

    Regression test for: "When a sweep starts without %gui qt or ensure_qt()
    run before, the Ipython kernel for jupyter lab will crash." Pre-fix the
    first ``s.start()`` killed the kernel (Qt qFatal abort); post-fix
    ``BaseSweep.start()`` sets up Qt automatically and the kernel survives.
    """
    nb = nbformat.read(QUICK_START, as_version=4)
    _strip_ensure_qt(nb)
    _execute_and_check_notebook(nb, tmp_path, temp_measureit_home, monkeypatch)
