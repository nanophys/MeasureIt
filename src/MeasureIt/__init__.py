from os.path import dirname, basename, isfile, join
import glob
from qcodes import config

config.logger.start_logging_on_import = "always"
config.logger.console_level = "WARNING"
config.station.enable_forced_reconnect = False

modules = glob.glob(join(dirname(__file__), "*.py"))
__all__ = [basename(f)[:-3] for f in modules if isfile(f) and not f.endswith("__init__.py")]

