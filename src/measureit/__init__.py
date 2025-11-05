import os
import sys
from importlib import metadata

from qcodes import config as qc_config

# Phase 2: stable top-level re-exports from subpackages
from .config import get_data_dir, get_path, set_data_dir  # noqa: F401
from .logging_utils import (  # noqa: F401
    attach_notebook_logging,
    ensure_sweep_logging,
    get_sweep_logger,
)
from .sweep.gate_leakage import GateLeakage  # noqa: F401
from .sweep.simul_sweep import SimulSweep  # noqa: F401
from .sweep.sweep0d import Sweep0D  # noqa: F401
from .sweep.sweep1d import Sweep1D  # noqa: F401
from .sweep.sweep2d import Sweep2D  # noqa: F401
from .sweep.sweep_ips import SweepIPS  # noqa: F401
from .tools.sweep_queue import DatabaseEntry, SweepQueue  # noqa: F401
from .tools.util import init_database  # noqa: F401

# Visualization helpers are available under measureit.visualization

qc_config.logger.start_logging_on_import = "always"
qc_config.logger.console_level = "WARNING"
qc_config.station.enable_forced_reconnect = False

__all__ = [
    "Sweep0D",
    "Sweep1D",
    "Sweep2D",
    "SimulSweep",
    "SweepIPS",
    "GateLeakage",
    "SweepQueue",
    "DatabaseEntry",
    "init_database",
    "get_path",
    "set_data_dir",
    "get_data_dir",
    "ensure_sweep_logging",
    "get_sweep_logger",
    "attach_notebook_logging",
]


try:
    __version__ = metadata.version("measureit")
except metadata.PackageNotFoundError:  # pragma: no cover - dev installs
    __version__ = "0.0.0"


# Display data directory info on first import (only in interactive sessions)
if hasattr(sys, "ps1") or "IPython" in sys.modules:
    _shown_key = "_measureit_data_dir_shown"
    if not hasattr(sys, _shown_key):
        setattr(sys, _shown_key, True)

        data_dir = get_data_dir()
        env_set = "MEASUREIT_HOME" in os.environ or "MeasureItHome" in os.environ

        print(f"\nMeasureIt data directory: {data_dir}")
        if not env_set:
            print("(Using platform default - set MEASUREIT_HOME to customize)")
        print("To change: measureit.set_data_dir('/path')\n")
