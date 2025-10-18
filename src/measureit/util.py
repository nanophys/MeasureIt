from ._deprecation import warn_deprecated as _md_warn

_md_warn("measureit.util", "measureit.tools.util")
from .tools.util import *  # re-export legacy path
