"""Qt testing helper functions."""

from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal


def assert_signal_emitted(qtbot, signal: pyqtSignal, timeout: int = 1000):
    """Assert that a signal is emitted within timeout.

    Args:
        qtbot: pytest-qt fixture
        signal: PyQt signal to wait for
        timeout: Timeout in milliseconds

    Raises:
        AssertionError: If signal is not emitted within timeout
    """
    with qtbot.waitSignal(signal, timeout=timeout) as blocker:
        assert blocker.signal_triggered, f"Signal {signal} was not emitted within {timeout}ms"


def assert_signal_not_emitted(qtbot, signal: pyqtSignal, wait_time: int = 100):
    """Assert that a signal is NOT emitted.

    Args:
        qtbot: pytest-qt fixture
        signal: PyQt signal to wait for
        wait_time: Time to wait in milliseconds

    Raises:
        AssertionError: If signal is emitted
    """
    with qtbot.waitSignal(signal, timeout=wait_time, raising=False) as blocker:
        assert not blocker.signal_triggered, f"Signal {signal} was unexpectedly emitted"


def wait_for_signal(qtbot, signal: pyqtSignal, timeout: int = 5000):
    """Wait for a signal to be emitted and return the arguments.

    Args:
        qtbot: pytest-qt fixture
        signal: PyQt signal to wait for
        timeout: Timeout in milliseconds

    Returns:
        Tuple of signal arguments

    Raises:
        TimeoutError: If signal is not emitted within timeout
    """
    with qtbot.waitSignal(signal, timeout=timeout) as blocker:
        pass
    return blocker.args


def wait_for_condition(qtbot, condition_func, timeout: int = 5000):
    """Wait for a condition function to return True.

    Args:
        qtbot: pytest-qt fixture
        condition_func: Callable that returns bool
        timeout: Timeout in milliseconds

    Raises:
        TimeoutError: If condition is not met within timeout
    """
    qtbot.waitUntil(condition_func, timeout=timeout)
