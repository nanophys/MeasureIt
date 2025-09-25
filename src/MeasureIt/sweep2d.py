from ._deprecation import warn_deprecated as _md_warn
_md_warn("MeasureIt.sweep2d", "MeasureIt.sweep.sweep2d")
from .sweep.sweep2d import Sweep2D
__all__ = ["Sweep2D"]
