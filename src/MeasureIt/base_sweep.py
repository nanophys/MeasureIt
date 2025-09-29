from ._deprecation import warn_deprecated as _md_warn
_md_warn("MeasureIt.base_sweep", "MeasureIt.sweep.base_sweep")
from .sweep.base_sweep import BaseSweep
__all__ = ["BaseSweep"]
