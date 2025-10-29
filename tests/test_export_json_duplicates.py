from qcodes import Station
from qcodes.instrument_drivers.mock_instruments import MockParabola

from measureit import SimulSweep, Sweep0D
from measureit.sweep.base_sweep import BaseSweep


def test_export_json_follow_params_duplicate_names(fast_sweep_kwargs):
    a = MockParabola(name="dupA")
    b = MockParabola(name="dupB")

    s = Sweep0D(max_time=0.1, **fast_sweep_kwargs)
    s.follow_param(a.parabola, b.parabola)

    j = s.export_json(fn=None)
    assert "follow_params" in j
    keys = set(j["follow_params"].keys())
    assert keys == {"dupA.parabola", "dupB.parabola"}

    # Verify import resolves both parameters without collision
    st = Station()
    st.add_component(a)
    st.add_component(b)
    s2 = BaseSweep.import_json(j, station=st)
    assert isinstance(s2, Sweep0D)
    assert len(s2._params) == 2
    inst_names = {p.instrument.name for p in s2._params}
    param_names = {p.name for p in s2._params}
    assert inst_names == {"dupA", "dupB"}
    assert param_names == {"parabola"}


def test_export_json_simulsweep_set_params_duplicate_names(fast_sweep_kwargs):
    x1 = MockParabola(name="sx1")
    x2 = MockParabola(name="sx2")

    set_params = {
        # Use integer-friendly values to avoid float rounding mismatches
        x1.x: {"start": 0.0, "stop": 2.0, "step": 1.0},
        x2.x: {"start": 0.0, "stop": 2.0, "step": 1.0},
    }
    s = SimulSweep(set_params, **fast_sweep_kwargs)

    j = s.export_json(fn=None)
    assert "set_params" in j
    keys = set(j["set_params"].keys())
    assert keys == {"sx1.x", "sx2.x"}

    st = Station()
    st.add_component(x1)
    st.add_component(x2)
    s2 = BaseSweep.import_json(j, station=st)
    assert isinstance(s2, SimulSweep)
    assert len(s2.set_params_dict) == 2
    inst_names = {p.instrument.name for p in s2.set_params_dict.keys()}
    param_names = {p.name for p in s2.set_params_dict.keys()}
    assert inst_names == {"sx1", "sx2"}
    assert param_names == {"x"}


def test_simulsweep_follow_excludes_set_params(fast_sweep_kwargs):
    a = MockParabola(name="sxA")
    b = MockParabola(name="sxB")

    set_params = {
        # Both have exactly two steps using integer-friendly values
        a.x: {"start": 0.0, "stop": 2.0, "step": 1.0},
        b.x: {"start": 10.0, "stop": 12.0, "step": 1.0},
    }
    s = SimulSweep(set_params, **fast_sweep_kwargs)
    # follow some extra params to simulate real usage
    s.follow_param(a.parabola, b.parabola)

    j = s.export_json(fn=None)
    sp_keys = set(j["set_params"].keys())
    fp_keys = set(j["follow_params"].keys())
    assert sp_keys.isdisjoint(fp_keys), "set_params must not overlap follow_params"
