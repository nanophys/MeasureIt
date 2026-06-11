"""Utilities for working with IPython/Jupyter frontends.

This module contains helpers that make it safer to enable the Qt event loop
from notebooks. On some Linux setups (notably WSL without the required X11
components) calling ``%gui qt`` will cause the kernel process to abort. We
probe Qt support in a separate subprocess first so we can present a helpful
message instead of crashing the notebook. Once Qt is known to work, the probe
can be bypassed by setting ``MEASUREIT_FORCE_QT=1`` or passing ``force=True``.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Optional

_QT_PROBE_SCRIPT = """
import sys

try:
    from PyQt5.QtWidgets import QApplication  # type: ignore
except Exception as exc:  # pragma: no cover - import errors are reported
    sys.stderr.write(f\"IMPORT_ERROR: {exc.__class__.__name__}: {exc}\\n\")
    raise

app = QApplication([])
app.quit()
"""


@dataclass
class _ProbeResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str

    @property
    def details(self) -> str:
        """Combined human-readable output."""
        output = self.stderr.strip() or self.stdout.strip()
        return output


# Cache a successful (slow, ~1s) subprocess probe for the lifetime of the
# process. Failures are re-probed so a user who fixes their environment
# mid-session can recover without restarting the kernel.
_probe_cache: _ProbeResult | None = None

# Keep a reference to any QApplication we create so it is not garbage
# collected (PyQt does not keep the instance alive on its own).
_qt_app = None
_qt_app_lock = threading.Lock()


def _is_wsl() -> bool:
    """Detect whether we are running inside Windows Subsystem for Linux."""
    if platform.system() != "Linux":
        return False

    try:
        with open("/proc/sys/kernel/osrelease", encoding="utf-8") as fh:
            return "microsoft" in fh.read().lower()
    except OSError:
        return False


def _probe_qt_support(timeout: float = 5.0) -> _ProbeResult:
    """Attempt to create a QApplication in a child process.

    Running the probe in a separate process isolates hard crashes (e.g. Qt
    calling ``abort()`` when the xcb plugin is missing) from the kernel.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _QT_PROBE_SCRIPT],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return _ProbeResult(
            ok=False,
            returncode=-1,
            stdout="",
            stderr=f"Qt probe timed out after {timeout} s: {exc}",
        )

    return _ProbeResult(
        ok=proc.returncode == 0,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def _probe_qt_support_cached(timeout: float = 5.0) -> _ProbeResult:
    """Run the Qt probe, reusing a previous successful result."""
    global _probe_cache
    if _probe_cache is None or not _probe_cache.ok:
        _probe_cache = _probe_qt_support(timeout=timeout)
    return _probe_cache


def _build_hint(details: str) -> Optional[str]:
    """Return a user-facing hint based on Qt error output."""
    lower = details.lower()

    if "no module named 'pyqt5'" in lower:
        return (
            "PyQt5 is not installed; install MeasureIt with the 'gui' extras "
            "or run `pip install PyQt5`."
        )

    if (
        'could not load the qt platform plugin "xcb" in "" even though it was found'
        in lower
    ):
        return (
            "Qt finds the XCB plugin but still cannot load it. Install the Qt GUI runtime "
            "libraries via `sudo apt install libqt5gui5 libegl1 libopengl0` and restart the kernel."
        )

    if 'could not load the qt platform plugin "xcb"' in lower:
        return (
            "Qt cannot load the XCB plugin. On WSL this usually means missing X11 "
            "dependencies. Install them via `sudo apt install libxcb-xinerama0 "
            "libxkbcommon-x11-0`, or run under WSLg/with an X server."
        )

    if "could not connect to display" in lower:
        return (
            "No display server is available. Ensure `$DISPLAY` is set and that "
            "WSLg or an X server is running before enabling Qt."
        )

    if "xcb" in lower and _is_wsl():
        return (
            "Qt reports XCB issues under WSL. Install the missing X11 libraries "
            "(e.g. `libxcb-xinerama0`, `libxkbcommon-x11-0`) or use WSLg."
        )

    if _is_wsl():
        return (
            "Qt failed to start under WSL. Verify that WSLg is enabled or that "
            "an X server is available, and that required X11 libraries are "
            "installed."
        )

    return None


def ensure_qt(
    event_loop: str = "qt",
    *,
    timeout: float = 5.0,
    verbose: bool = True,
    force: bool = False,
) -> bool:
    """Enable the Qt event loop in IPython after verifying Qt can start safely.

    Parameters
    ----------
    event_loop:
        The GUI event loop identifier understood by IPython (defaults to ``"qt"``).
    timeout:
        Maximum number of seconds to wait for the probe process to finish.
    verbose:
        When ``True`` prints diagnostic information if Qt cannot be initialised.
    force:
        When ``True`` (or the environment variable ``MEASUREIT_FORCE_QT`` is set to a
        truthy value) skip the safety probe and attempt to enable Qt regardless.

    Returns:
    -------
    bool
        ``True`` if the Qt event loop was enabled, ``False`` if the probe failed.
    """
    try:
        from IPython import get_ipython  # Lazy import to avoid mandatory dependency.
    except ImportError:  # pragma: no cover - IPython not available
        if verbose:
            print("IPython is not installed; cannot enable Qt integration.")
        return False

    ip = get_ipython()
    if ip is None:
        if verbose:
            print("No active IPython shell detected; skipping Qt integration.")
        return False

    active = getattr(ip, "active_eventloop", None)
    if active == event_loop:
        return True

    force_env = os.environ.get("MEASUREIT_FORCE_QT", "").strip().lower()
    if force_env in {"1", "true", "yes", "on"}:
        force = True

    if not force:
        probe = _probe_qt_support_cached(timeout=timeout)
        if not probe.ok:
            if verbose:
                print("WARNING: Skipping Qt integration because the probe failed.")
                details = probe.details
                if details:
                    print(details)
                hint = _build_hint(details)
                if hint:
                    print(hint)
                if os.environ.get("MEASUREIT_FORCE_QT") is None:
                    print(
                        "Set MEASUREIT_FORCE_QT=1 to bypass the probe once your Qt setup is ready."
                    )
            return False
    elif verbose:
        print("Forcing Qt integration without running the safety probe.")

    try:
        ip.enable_gui(event_loop)
    except Exception as exc:  # pragma: no cover - defensive guard
        if verbose:
            print(f"Failed to enable Qt integration: {exc}")
        return False

    return True


def ensure_qt_app_for_plotting(*, timeout: float = 5.0, verbose: bool = False) -> bool:
    """Make sure a QApplication exists so plot widgets can be created safely.

    Creating a ``QWidget`` without a ``QApplication`` makes Qt abort the whole
    process — in Jupyter this kills the kernel. This helper is called before
    any plot widgets are constructed. Under IPython it also enables the ``qt``
    event loop (via :func:`ensure_qt`) so plot windows stay responsive, then
    instantiates a ``QApplication`` if one still does not exist. A successful
    run of the slow subprocess safety probe is cached for the process
    lifetime; failures are re-probed on the next call.

    Returns:
    -------
    bool
        ``True`` if it is safe to create Qt widgets, ``False`` if Qt cannot be
        started safely (callers should then skip plotting).
    """
    if os.environ.get("MEASUREIT_FAKE_QT", "").lower() in {"1", "true", "yes"}:
        # Test stubs replace Qt entirely; widget creation cannot crash.
        return True

    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:
        return False

    # Enable the IPython Qt event loop first so windows are responsive, not
    # just non-crashing. ensure_qt() is a no-op if the loop is already active
    # and probes Qt support safely in a subprocess otherwise.
    try:
        from IPython import get_ipython
    except ImportError:
        ip = None
    else:
        ip = get_ipython()

    if ip is not None and getattr(ip, "active_eventloop", None) != "qt":
        ensure_qt(timeout=timeout, verbose=verbose)

    if QApplication.instance() is not None:
        return True

    # enable_gui() registers the event loop but does not necessarily create a
    # QApplication synchronously (and outside IPython nothing has). Only
    # create one ourselves if Qt can start without aborting the process.
    force_env = os.environ.get("MEASUREIT_FORCE_QT", "").strip().lower()
    if force_env not in {"1", "true", "yes", "on"}:
        if not _probe_qt_support_cached(timeout=timeout).ok:
            return False

    global _qt_app
    with _qt_app_lock:
        if QApplication.instance() is None:
            _qt_app = QApplication(["measureit"])
    return True


__all__ = ["ensure_qt", "ensure_qt_app_for_plotting"]
