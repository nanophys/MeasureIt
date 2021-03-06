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
