"""Helpers for locating and managing the MeasureIt data directory.

The data directory stores experiment databases, log files, configuration
snapshots, and exported origin files. Users can override the location either by
setting the ``MEASUREIT_HOME`` environment variable, keeping the legacy
``MeasureItHome`` environment variable, or by calling :func:`set_data_dir`.

Examples:
--------
>>> from measureit.config import set_data_dir, get_path
>>> set_data_dir("/tmp/custom_measureit")
>>> get_path("databases")
PosixPath('/tmp/custom_measureit/Databases')
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional

from platformdirs import user_data_dir

_DATA_DIR_OVERRIDE: Optional[Path] = None

_SUBDIR_NAMES: Dict[str, str] = {
    "databases": "Databases",
    "logs": "logs",
    "cfg": "cfg",
    "origin_files": "Origin Files",
}


def set_data_dir(path: os.PathLike[str] | str) -> Path:
    """Override the base directory used for MeasureIt data files.

    Parameters
    ----------
    path
        Absolute or relative path to use as the root of all MeasureIt data.

    Returns:
    -------
    pathlib.Path
        The normalised absolute directory that will be used going forward.
    """
    global _DATA_DIR_OVERRIDE

    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = candidate.resolve(strict=False)

    _DATA_DIR_OVERRIDE = candidate
    os.environ["MEASUREIT_HOME"] = str(candidate)
    os.environ["MeasureItHome"] = str(candidate)
    return candidate


def get_path(subdir: str) -> Path:
    """Return the path for a known MeasureIt data sub-directory.

    The directory is created on first access to keep the file-system layout
    lazy.

    Parameters
    ----------
    subdir
        One of ``\"databases\"``, ``\"logs\"``, ``\"cfg\"``, or ``\"origin_files\"``.

    Returns:
    -------
    pathlib.Path
        The absolute path to the requested directory.

    Raises:
    ------
    ValueError
        If *subdir* is not a recognised directory key.
    """
    try:
        folder_name = _SUBDIR_NAMES[subdir]
    except KeyError as exc:  # pragma: no cover - defensive programming
        raise ValueError(f"Unknown MeasureIt data directory: {subdir!r}") from exc

    base = _determine_base_dir()
    base.mkdir(parents=True, exist_ok=True)
    target = base / folder_name
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_data_dir() -> Path:
    """Return the base directory used for all MeasureIt data files.

    Returns the directory determined by (in priority order):
    1. Runtime override via :func:`set_data_dir`
    2. ``MEASUREIT_HOME`` environment variable
    3. ``MeasureItHome`` environment variable (legacy)
    4. Platform-specific default (e.g., ``~/Library/Application Support/measureit`` on macOS)

    Returns:
    -------
    pathlib.Path
        The absolute path to the MeasureIt data directory.

    Examples:
    --------
    >>> from measureit import get_data_dir
    >>> print(get_data_dir())
    /Users/username/Library/Application Support/measureit
    """
    return _determine_base_dir()


def _determine_base_dir() -> Path:
    """Determine the root directory according to overrides and environment."""
    if _DATA_DIR_OVERRIDE is not None:
        base = _DATA_DIR_OVERRIDE
    else:
        env = os.environ.get("MEASUREIT_HOME")
        legacy_env = os.environ.get("MeasureItHome")
        if env:
            base = Path(env).expanduser()
        elif legacy_env:
            base = Path(legacy_env).expanduser()
        else:
            base = Path(user_data_dir("measureit", "measureit")).expanduser()
        # Normalise and remember the resolved path for downstream use
        if not base.is_absolute():
            base = base.resolve(strict=False)
        os.environ.setdefault("MEASUREIT_HOME", str(base))
        os.environ.setdefault("MeasureItHome", str(base))

    return base


__all__ = ["get_path", "set_data_dir", "get_data_dir"]
