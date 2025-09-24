import pytest

import qcodes as qc
from qcodes.instrument_drivers.mock_instruments import MockParabola

from MeasureIt.base_sweep import BaseSweep
from MeasureIt.sweep0d import Sweep0D
from MeasureIt.simul_sweep import SimulSweep
from qcodes import Station


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
        x1.x: {"start": 0.0, "stop": 0.2, "step": 0.1},
        x2.x: {"start": 0.0, "stop": 0.2, "step": 0.1},
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

