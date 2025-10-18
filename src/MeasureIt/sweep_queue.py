from ._deprecation import warn_deprecated as _md_warn

_md_warn("measureit.sweep_queue", "measureit.tools.sweep_queue")
from .tools.sweep_queue import DatabaseEntry, SweepQueue

__all__ = ["SweepQueue", "DatabaseEntry"]
