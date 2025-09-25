from ._deprecation import warn_deprecated as _md_warn
_md_warn("MeasureIt.gate_leakage", "MeasureIt.sweep.gate_leakage")
from .sweep.gate_leakage import GateLeakage
__all__ = ["GateLeakage"]
