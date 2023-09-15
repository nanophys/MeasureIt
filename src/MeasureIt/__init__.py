from os.path import dirname, basename, isfile, join
import glob
import os
from qcodes import config

config.core.db_location = f"{os.environ['MeasureItHome']}\\Databases\\default.db"
config.logger.start_logging_on_import = 'always'
config.logger.console_level = 'WARNING'
config.station.enable_forced_reconnect = False
config.station.default_folder = f"{os.environ['MeasureItHome']}\\cfg\\"
config.station.default_file = f"{os.environ['MeasureItHome']}\\cfg\\default.station.yaml"

config.save_config(f"{os.environ['MeasureItHome']}\\cfg\\qcodesrc.json")
config.save_schema(f"{os.environ['MeasureItHome']}\\cfg\\qcodesrc_schema.json")
config.save_to_home()

from .sweep0d import Sweep0D
from .sweep1d import Sweep1D
from .sweep2d import Sweep2D
from .sweep_queue import SweepQueue, DatabaseEntry
from .sweep_ips import SweepIPS
from .simul_sweep import SimulSweep
from . import util
from .safe_ramp import safe_ramp
from .gate_leakage import GateLeakage

modules = glob.glob(join(dirname(__file__), "*.py"))
__all__ = [basename(f)[:-3] for f in modules if isfile(f) and not f.endswith('__init__.py')]
