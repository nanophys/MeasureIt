from ._deprecation import warn_deprecated as _md_warn
_md_warn("MeasureIt.sweep1d_listening", "MeasureIt.sweep.sweep1d_listening")
from .sweep.sweep1d_listening import Sweep1D_listening
__all__ = ["Sweep1D_listening"]
