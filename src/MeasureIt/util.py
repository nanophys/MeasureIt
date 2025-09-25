from ._deprecation import warn_deprecated as _md_warn
_md_warn("MeasureIt.util", "MeasureIt.tools.util")
from .tools.util import *  # re-export legacy path
