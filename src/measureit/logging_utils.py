# logging_utils.py
"""Shared logging helpers for MeasureIt sweeps and tooling.

This module configures a dedicated logger hierarchy for sweep execution. It
provides both a rotating file handler (written under the MeasureIt *logs*
directory) and a stream handler so messages remain visible in interactive
sessions. An optional notebook handler routes records back onto the IPython
event loop, ensuring messages appear inside Jupyter notebook cells even when
emitted from worker threads.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime
from typing import Optional

from .config import get_path

_LOGGER_NAME = "measureit.sweeps"
_CONFIGURED = False


def ensure_sweep_logging(use_stream: bool = True) -> logging.Logger:
    """Initialise and return the root sweep logger.

    Parameters
    ----------
    use_stream:
        When True (default) a :class:`logging.StreamHandler` targeting stdout is
        attached in addition to the rotating file handler. Disable when the
        caller wants to provide bespoke stream routing.

    Returns
    -------
    logging.Logger
        The configured sweep logger that other modules can use/derive from.
    """

    global _CONFIGURED

    logger = logging.getLogger(_LOGGER_NAME)
    if _CONFIGURED:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    log_dir: Path = get_path("logs")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"sweeps_{timestamp}.log"

    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5
    )
    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    if use_stream:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(logging.INFO)
        logger.addHandler(stream_handler)

    _CONFIGURED = True
    return logger


def get_sweep_logger(suffix: Optional[str] = None) -> logging.Logger:
    """Return a child logger for sweep-related components."""

    base = ensure_sweep_logging()
    if suffix:
        return base.getChild(suffix)
    return base


class NotebookHandler(logging.Handler):
    """A logging handler that marshals records onto the IPython event loop."""

    def __init__(self, loop=None):
        super().__init__()
        self._loop = loop

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - UI code
        msg = self.format(record)
        try:
            loop = self._loop
            if loop is None:
                from IPython import get_ipython

                ip = get_ipython()
                loop = getattr(getattr(ip, "kernel", None), "io_loop", None)

            if loop is not None:
                loop.call_soon_threadsafe(print, msg)
            else:
                print(msg)
        except Exception:
            print(msg)


def attach_notebook_logging(loop=None) -> NotebookHandler:
    """Attach a NotebookHandler to the sweep logger and return it."""

    logger = ensure_sweep_logging()
    handler = NotebookHandler(loop=loop)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return handler


__all__ = [
    "ensure_sweep_logging",
    "get_sweep_logger",
    "attach_notebook_logging",
    "NotebookHandler",
]
