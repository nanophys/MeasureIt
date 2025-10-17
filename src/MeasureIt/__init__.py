from importlib import metadata

from qcodes import config as qc_config

# Phase 2: stable top-level re-exports from subpackages
from .config import get_path, set_data_dir  # noqa: F401
from .sweep.sweep0d import Sweep0D  # noqa: F401
from .sweep.sweep1d import Sweep1D  # noqa: F401
from .sweep.sweep2d import Sweep2D  # noqa: F401
from .sweep.simul_sweep import SimulSweep  # noqa: F401
from .sweep.sweep_ips import SweepIPS  # noqa: F401
from .sweep.gate_leakage import GateLeakage  # noqa: F401

from .tools.sweep_queue import SweepQueue, DatabaseEntry  # noqa: F401
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
]


try:
    __version__ = metadata.version("measureit")
except metadata.PackageNotFoundError:  # pragma: no cover - dev installs
    __version__ = "0.0.0"
