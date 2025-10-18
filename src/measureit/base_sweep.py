from ._deprecation import warn_deprecated as _md_warn

_md_warn("measureit.base_sweep", "measureit.sweep.base_sweep")
from .sweep.base_sweep import BaseSweep

__all__ = ["BaseSweep"]
