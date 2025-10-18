from ._deprecation import warn_deprecated as _md_warn

_md_warn("measureit.sweep_ips", "measureit.sweep.sweep_ips")
from .sweep.sweep_ips import SweepIPS

__all__ = ["SweepIPS"]
