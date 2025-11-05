import importlib


def test_logging_exports_available():
    measureit = importlib.import_module("measureit")
    assert hasattr(measureit, "ensure_sweep_logging")
    assert hasattr(measureit, "get_sweep_logger")
    assert hasattr(measureit, "attach_notebook_logging")


def test_sweep_logging_helpers():
    from measureit import attach_notebook_logging, ensure_sweep_logging, get_sweep_logger
    from measureit.logging_utils import NotebookHandler

    base_logger = ensure_sweep_logging()
    child = get_sweep_logger("unit_test")
    assert child.name.endswith("unit_test")

    handler = attach_notebook_logging()
    try:
        assert isinstance(handler, NotebookHandler)
        assert handler in base_logger.handlers
    finally:
        base_logger.removeHandler(handler)
