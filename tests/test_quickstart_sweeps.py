import qcodes as qc
from qcodes.instrument_drivers.mock_instruments import MockParabola

from measureit import get_path
from measureit.sweep import Sweep0D, Sweep1D, Sweep2D
from measureit.tools import init_database


def test_sweep0d_runs_headless(qtbot, fast_sweep_kwargs):
    inst = MockParabola(name="m0d")
    inst.noise(0.1)
    s = Sweep0D(max_time=0.2, **fast_sweep_kwargs)
    s.follow_param(inst.parabola, inst.skewed_parabola)

    with qtbot.waitSignal(s.completed, timeout=4000):
        s.start()
    s.kill()


def test_sweep1d_runs_headless(qtbot, fast_sweep_kwargs):
    inst = MockParabola(name="m1d")
    inst.noise(0.1)
    s = Sweep1D(inst.x, start=0.0, stop=0.2, step=0.1, **fast_sweep_kwargs)
    s.follow_param(inst.parabola, inst.skewed_parabola)

    with qtbot.waitSignal(s.completed, timeout=4000):
        s.start()
    s.kill()


def test_sweep2d_runs_headless(qtbot, fast_sweep_kwargs):
    # Use two independent mock instruments for inner/outer params
    inner = MockParabola(name="inner")
    outer = MockParabola(name="outer")
    inner.noise(0.1)
    outer.noise(0.1)

    in_params = [inner.x, 0.0, 0.2, 0.1]  # 3 points
    out_params = [outer.x, 0.0, 0.2, 0.2]  # 2 rows

    s = Sweep2D(in_params, out_params, outer_delay=0.0, **fast_sweep_kwargs)
    s.follow_param(inner.parabola)
    # Speed: don't do bidirectional inner lines during tests
    s.in_sweep.bidirectional = False
    with qtbot.waitSignal(s.completed, timeout=5000):
        s.start(ramp_to_start=False)
    s.kill()


def test_database_save_and_dataset_signal(qtbot, temp_measureit_home):
    # Database-backed short 1D sweep
    inst = MockParabola(name="mdb")
    inst.noise(0.0)

    # Save to DB; keep plotting off
    s = Sweep1D(
        inst.x,
        start=0.0,
        stop=0.2,
        step=0.1,
        inter_delay=0.01,
        save_data=True,
        plot_data=False,
        suppress_output=True,
    )
    s.follow_param(inst.parabola)

    # Setup DB
    db_name = "test_quickstart"
    exp_name = "pytest_exp"
    sample_name = "pytest_sample"
    init_database(db_name, exp_name, sample_name, s)

    with qtbot.waitSignal(s.completed, timeout=5000):
        s.start()
    s.kill()

    # Check DB path
    db_dir = get_path("databases")
    assert db_dir.parent == temp_measureit_home
    db_file = db_dir / f"{db_name}.db"
    assert db_file.exists(), f"Database file not found: {db_file}"

    # Verify database has an experiment via QCoDeS
    qc.dataset.initialise_or_create_database_at(str(db_file))
    exps = list(qc.dataset.experiment_container.experiments())
    assert len(exps) >= 1
    assert exps[-1].name == exp_name
    assert exps[-1].sample_name == sample_name
