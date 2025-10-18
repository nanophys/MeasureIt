from ._deprecation import warn_deprecated as _md_warn

_md_warn("measureit.sweep1d", "measureit.sweep.sweep1d")
from .sweep.sweep1d import Sweep1D

__all__ = ["Sweep1D"]
