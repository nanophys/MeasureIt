import json

import qcodes as qc
from qcodes.dataset.data_set import load_by_run_spec
from qcodes.instrument_drivers.mock_instruments import MockParabola

from measureit.sweep import Sweep0D, Sweep1D, Sweep2D
from measureit.tools import init_database


def _load_ds(captured):
    qc.dataset.initialise_or_create_database_at(captured["db"])
    return load_by_run_spec(
        experiment_name=captured["exp name"],
        sample_name=captured["sample name"],
        captured_run_id=captured["run id"],
    )


def test_sweep0d_metadata_written(qtbot, temp_measureit_home):
    p = MockParabola(name="m0d")
    p.noise(0.0)

    s = Sweep0D(
        max_time=0.05,
        inter_delay=0.01,
        save_data=True,
        plot_data=False,
        suppress_output=True,
    )
    s.follow_param(p.parabola)

    init_database("test_meta0d", "pytest_meta0d", "sample_meta0d", s)

    captured = {}
    s.dataset_signal.connect(lambda ds: captured.update(ds))

    with qtbot.waitSignal(s.completed, timeout=5000):
        s.start()
    s.kill()

    assert captured, "No dataset info captured from Sweep0D"
    ds = _load_ds(captured)
    meta_map = getattr(ds, "metadata", {}) or {}
    assert "measureit" in meta_map, (
        "Expected 'measureit' metadata to be present for Sweep0D"
    )
    meta = (
        json.loads(meta_map["measureit"])
        if isinstance(meta_map["measureit"], str)
        else meta_map["measureit"]
    )
    assert meta.get("class") == "Sweep0D"


def test_sweep1d_metadata_written(qtbot, temp_measureit_home):
    p = MockParabola(name="m1d")
    p.noise(0.0)

    s = Sweep1D(
        p.x,
        start=0.0,
        stop=0.1,
        step=0.1,
        inter_delay=0.01,
        save_data=True,
        plot_data=False,
        suppress_output=True,
    )
    s.follow_param(p.parabola)

    init_database("test_meta1d", "pytest_meta1d", "sample_meta1d", s)

    captured = {}
    s.dataset_signal.connect(lambda ds: captured.update(ds))

    with qtbot.waitSignal(s.completed, timeout=5000):
        s.start(ramp_to_start=False)
    s.kill()

    assert captured, "No dataset info captured from Sweep1D"
    ds = _load_ds(captured)
    meta_map = getattr(ds, "metadata", {}) or {}
    assert "measureit" in meta_map, (
        "Expected 'measureit' metadata to be present for Sweep1D"
    )
    meta = (
        json.loads(meta_map["measureit"])
        if isinstance(meta_map["measureit"], str)
        else meta_map["measureit"]
    )
    assert meta.get("class") == "Sweep1D"


def test_sweep2d_metadata_prefers_outer_and_writes_once(qtbot, temp_measureit_home):
    # Setup two mock instruments
    inner = MockParabola(name="m_in")
    outer = MockParabola(name="m_out")
    inner.noise(0.0)
    outer.noise(0.0)

    # Minimal, fast 2D sweep
    in_params = [inner.x, 0.0, 0.1, 0.1]  # 1 inner step
    out_params = [outer.x, 0.0, 0.1, 0.1]  # 1 outer row

    s = Sweep2D(
        in_params,
        out_params,
        outer_delay=0.0,
        inter_delay=0.01,
        save_data=True,
        plot_data=False,
        suppress_output=True,
    )
    s.in_sweep.bidirectional = False

    init_database("test_meta2d", "pytest_meta2d", "sample_meta2d", s)

    # Capture dataset info from inner and outer signals (inner creates it)
    captured = {}
    s.dataset_signal.connect(lambda ds: captured.update(ds))
    s.in_sweep.dataset_signal.connect(lambda ds: captured.update(ds))

    with qtbot.waitSignal(s.completed, timeout=5000):
        s.start(ramp_to_start=False)
    s.kill()

    assert captured, "No dataset info captured from Sweep2D"
    ds = _load_ds(captured)
    meta_map = getattr(ds, "metadata", {}) or {}
    assert "measureit" in meta_map, (
        "Expected 'measureit' metadata to be present for Sweep2D"
    )
    meta = (
        json.loads(meta_map["measureit"])
        if isinstance(meta_map["measureit"], str)
        else meta_map["measureit"]
    )
    assert meta.get("class") == "Sweep2D", (
        f"Expected class 'Sweep2D' in metadata, got {meta.get('class')}"
    )
