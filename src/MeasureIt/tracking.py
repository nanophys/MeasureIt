from ._deprecation import warn_deprecated as _md_warn
_md_warn("MeasureIt.tracking", "MeasureIt.tools.tracking")
from .tools.tracking import *  # re-export legacy path
