from ._deprecation import warn_deprecated as _md_warn
_md_warn("MeasureIt.sweep0d", "MeasureIt.sweep.sweep0d")
from .sweep.sweep0d import Sweep0D
__all__ = ["Sweep0D"]
