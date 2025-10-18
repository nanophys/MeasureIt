from ._deprecation import warn_deprecated as _md_warn

_md_warn("measureit.tracking", "measureit.tools.tracking")
from .tools.tracking import *  # re-export legacy path
