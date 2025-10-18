from ._deprecation import warn_deprecated as _md_warn

_md_warn("measureit.gate_leakage", "measureit.sweep.gate_leakage")
from .sweep.gate_leakage import GateLeakage

__all__ = ["GateLeakage"]
