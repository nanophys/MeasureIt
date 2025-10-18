from ._deprecation import warn_deprecated as _md_warn

_md_warn("measureit.simul_sweep", "measureit.sweep.simul_sweep")
from .sweep.simul_sweep import SimulSweep

__all__ = ["SimulSweep"]
