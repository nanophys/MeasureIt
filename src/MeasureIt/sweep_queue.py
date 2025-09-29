from ._deprecation import warn_deprecated as _md_warn
_md_warn("MeasureIt.sweep_queue", "MeasureIt.tools.sweep_queue")
from .tools.sweep_queue import SweepQueue, DatabaseEntry
__all__ = ["SweepQueue", "DatabaseEntry"]
