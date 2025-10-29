#!/usr/bin/env python3
"""Quick verification that measureit is installed correctly."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path


def test_import() -> bool:
    """Test basic package import."""
    try:
        import measureit  # noqa: F401
    except ImportError as exc:
        print(f"[fail] Import failed: {exc}")
        return False
    else:
        print("[ ok ] measureit imports successfully")
        return True


def test_config() -> bool:
    """Ensure get_path/set_data_dir behave as expected."""
    tmp_dir: Path | None = None
    try:
        import measureit

        default_db = measureit.get_path("databases")
        print(f"[ ok ] get_path('databases') -> {default_db}")

        tmp_dir = Path(tempfile.mkdtemp(prefix="measureit-smoke-")).resolve()
        measureit.set_data_dir(tmp_dir)
        custom_db = measureit.get_path("databases").resolve()
        try:
            custom_db.relative_to(tmp_dir)
        except ValueError as exc:
            raise AssertionError(
                f"Custom data dir {custom_db} not under {tmp_dir}"
            ) from exc
        print(f"[ ok ] set_data_dir override -> {custom_db}")
        return True
    except Exception as exc:  # pragma: no cover - diagnostic script
        print(f"[fail] Config test failed: {exc}")
        return False
    finally:
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)


def test_core_imports() -> bool:
    """Validate core sweep and queue classes are importable."""
    try:
        from measureit import (  # noqa: F401
            GateLeakage,
            SimulSweep,
            Sweep0D,
            Sweep1D,
            Sweep2D,
            SweepIPS,
            SweepQueue,
        )
        from measureit.base_sweep import BaseSweep  # noqa: F401
        from measureit.tools import init_database  # noqa: F401
    except ImportError as exc:
        print(f"[fail] Core imports failed: {exc}")
        return False
    else:
        print("[ ok ] Core sweep classes import successfully")
        return True


def test_pyqt() -> bool:
    """Smoke-test that PyQt5 can be imported alongside measureit."""
    try:
        from PyQt5.QtCore import QObject  # noqa: F401

        from measureit._internal.runner_thread import RunnerThread  # noqa: F401
        from measureit.base_sweep import BaseSweep  # noqa: F401
    except ImportError as exc:
        print(f"[fail] PyQt5 test failed: {exc}")
        return False
    else:
        print("[ ok ] PyQt5 integration imports cleanly")
        return True


def main() -> int:
    tests = [
        test_import,
        test_config,
        test_core_imports,
        test_pyqt,
    ]

    results = [fn() for fn in tests]
    if all(results):
        print("\n=== All tests passed! measureit is ready to use ===")
        return 0

    print("\n*** Some tests failed. Check installation. ***")
    return 1


if __name__ == "__main__":
    sys.exit(main())
