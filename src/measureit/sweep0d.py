from ._deprecation import warn_deprecated as _md_warn

_md_warn("measureit.sweep0d", "measureit.sweep.sweep0d")
from .sweep.sweep0d import Sweep0D

__all__ = ["Sweep0D"]
