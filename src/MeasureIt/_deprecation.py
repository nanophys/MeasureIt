import warnings


def warn_deprecated(old: str, new: str) -> None:
    """Always emit a FutureWarning for an old import path.

    FutureWarning is visible by default in most environments (unlike
    DeprecationWarning), so users will see guidance without changing
    warning filters.
    """
    warnings.warn(
        f"{old} will deprecated soon; use {new}",
        FutureWarning,
        stacklevel=2,
    )
