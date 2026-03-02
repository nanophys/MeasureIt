"""Tests for array-valued parameter (ParameterWithSetpoints) support.

Covers spectrometer-style and VNA-style instruments that return arrays per get().
"""

import numpy as np
import pytest
from qcodes.parameters import Parameter

from measureit.tools.util import is_array_parameter, is_numeric_parameter


# ---------------------------------------------------------------------------
# is_array_parameter
# ---------------------------------------------------------------------------
class TestIsArrayParameter:
    def test_scalar_not_detected(self, mock_parameter):
        p = mock_parameter("voltage", unit="V", label="Voltage")
        assert is_array_parameter(p) is False

    def test_spectrometer_spectrum_detected(self, mock_spectrometer):
        spec = mock_spectrometer()
        assert is_array_parameter(spec.spectrum) is True

    def test_vna_s21_detected(self, mock_vna):
        vna = mock_vna()
        assert is_array_parameter(vna.s21_magnitude) is True

    def test_vna_s21_phase_detected(self, mock_vna):
        vna = mock_vna()
        assert is_array_parameter(vna.s21_phase) is True

    def test_vna_scalar_power_not_detected(self, mock_vna):
        vna = mock_vna()
        assert is_array_parameter(vna.power) is False


# ---------------------------------------------------------------------------
# is_numeric_parameter (with array params)
# ---------------------------------------------------------------------------
class TestIsNumericParameterWithArrays:
    def test_array_params_are_numeric(self, mock_spectrometer):
        spec = mock_spectrometer()
        assert is_numeric_parameter(spec.spectrum) is True

    def test_vna_array_params_are_numeric(self, mock_vna):
        vna = mock_vna()
        assert is_numeric_parameter(vna.s21_magnitude) is True

    def test_scalar_still_numeric(self, mock_parameter):
        p = mock_parameter("voltage", unit="V", label="Voltage")
        assert is_numeric_parameter(p) is True

    def test_string_param_rejected(self):
        from qcodes.validators import Strings

        p = Parameter("mode", vals=Strings(), set_cmd=None, get_cmd=lambda: "abc")
        assert is_numeric_parameter(p) is False


# ---------------------------------------------------------------------------
# follow_param acceptance
# ---------------------------------------------------------------------------
class TestFollowParam:
    def test_spectrometer_accepted(self, mock_spectrometer, mock_parameter, fast_sweep_kwargs):
        from measureit.sweep import Sweep1D

        spec = mock_spectrometer()
        gate = mock_parameter("gate", unit="V", label="Gate")
        s = Sweep1D(gate, 0, 1, 0.1, **fast_sweep_kwargs)
        s.follow_param(spec.spectrum)
        assert spec.spectrum in s._params

    def test_vna_accepted(self, mock_vna, mock_parameter, fast_sweep_kwargs):
        from measureit.sweep import Sweep1D

        vna = mock_vna()
        gate = mock_parameter("gate", unit="V", label="Gate")
        s = Sweep1D(gate, 0, 1, 0.1, **fast_sweep_kwargs)
        s.follow_param(vna.s21_magnitude)
        assert vna.s21_magnitude in s._params

    def test_mixed_scalar_and_array(self, mock_spectrometer, mock_parameter, fast_sweep_kwargs):
        from measureit.sweep import Sweep1D

        spec = mock_spectrometer()
        gate = mock_parameter("gate", unit="V", label="Gate")
        scalar = mock_parameter("current", unit="A", label="Current")
        s = Sweep1D(gate, 0, 1, 0.1, **fast_sweep_kwargs)
        s.follow_param(spec.spectrum, scalar)
        assert spec.spectrum in s._params
        assert scalar in s._params


# ---------------------------------------------------------------------------
# _create_measurement and check_params_are_correct
# ---------------------------------------------------------------------------
class TestCreateMeasurement:
    def test_spectrometer_setpoints_registered(
        self, mock_spectrometer, mock_parameter, fast_sweep_kwargs, temp_database
    ):
        from measureit.sweep import Sweep1D

        spec = mock_spectrometer()
        gate = mock_parameter("gate", unit="V", label="Gate")
        s = Sweep1D(gate, 0, 1, 0.1, **fast_sweep_kwargs)
        s.follow_param(spec.spectrum)
        s._create_measurement()
        # QCoDeS prefixes with instrument name: "spectrometer_pixels"
        setpoint_name = str(spec.pixels)
        assert setpoint_name in s.meas.parameters

    def test_vna_setpoints_registered(
        self, mock_vna, mock_parameter, fast_sweep_kwargs, temp_database
    ):
        from measureit.sweep import Sweep1D

        vna = mock_vna()
        gate = mock_parameter("gate", unit="V", label="Gate")
        s = Sweep1D(gate, 0, 1, 0.1, **fast_sweep_kwargs)
        s.follow_param(vna.s21_magnitude)
        s._create_measurement()
        setpoint_name = str(vna.frequency)
        assert setpoint_name in s.meas.parameters

    def test_check_params_correct_with_spectrometer(
        self, mock_spectrometer, mock_parameter, fast_sweep_kwargs, temp_database
    ):
        from measureit.sweep import Sweep1D

        spec = mock_spectrometer()
        gate = mock_parameter("gate", unit="V", label="Gate")
        s = Sweep1D(gate, 0, 1, 0.1, **fast_sweep_kwargs)
        s.follow_param(spec.spectrum)
        s._create_measurement()
        assert s.check_params_are_correct() is True

    def test_check_params_correct_with_vna(
        self, mock_vna, mock_parameter, fast_sweep_kwargs, temp_database
    ):
        from measureit.sweep import Sweep1D

        vna = mock_vna()
        gate = mock_parameter("gate", unit="V", label="Gate")
        s = Sweep1D(gate, 0, 1, 0.1, **fast_sweep_kwargs)
        s.follow_param(vna.s21_magnitude, vna.s21_phase)
        s._create_measurement()
        assert s.check_params_are_correct() is True


# ---------------------------------------------------------------------------
# Plotter array → scalar reduction
# ---------------------------------------------------------------------------
class TestPlotterArrayReduction:
    def test_spectrometer_array_reduced_to_sum(self, mock_spectrometer):
        spec = mock_spectrometer()
        arr = spec.spectrum.get()
        assert arr.ndim == 1
        assert len(arr) == 128
        expected = float(np.sum(arr))
        # Simulate what the plotter does
        if is_array_parameter(spec.spectrum) and hasattr(arr, "__len__"):
            result = float(np.sum(arr))
        else:
            result = float(np.array(arr).flatten()[0])
        assert result == pytest.approx(expected)

    def test_vna_array_reduced_to_sum(self, mock_vna):
        vna = mock_vna()
        arr = vna.s21_magnitude.get()
        assert arr.ndim == 1
        assert len(arr) == 201
        expected = float(np.sum(arr))
        if is_array_parameter(vna.s21_magnitude) and hasattr(arr, "__len__"):
            result = float(np.sum(arr))
        else:
            result = float(np.array(arr).flatten()[0])
        assert result == pytest.approx(expected)

    def test_scalar_backward_compat(self, mock_parameter):
        p = mock_parameter("voltage", initial_value=3.14, unit="V", label="Voltage")
        val = p.get()
        if is_array_parameter(p) and hasattr(val, "__len__"):
            result = float(np.sum(val))
        elif hasattr(val, "flatten"):
            result = float(np.array(val).flatten()[0])
        else:
            result = float(val)
        assert result == pytest.approx(3.14)


# ---------------------------------------------------------------------------
# Sweep1D construction with array instruments
# ---------------------------------------------------------------------------
class TestSweep1DWithSpectrometer:
    def test_create_sweep_with_spectrum(self, mock_spectrometer, mock_parameter, fast_sweep_kwargs):
        from measureit.sweep import Sweep1D

        spec = mock_spectrometer()
        gate = mock_parameter("gate", unit="V", label="Gate")
        scalar = mock_parameter("current", unit="A", label="Current")
        s = Sweep1D(gate, 0, 1, 0.1, **fast_sweep_kwargs)
        s.follow_param(spec.spectrum, scalar)
        assert len(s._params) == 2
        assert spec.spectrum in s._params
        assert scalar in s._params


class TestSweep1DWithVNA:
    def test_create_sweep_with_vna(self, mock_vna, mock_parameter, fast_sweep_kwargs):
        from measureit.sweep import Sweep1D

        vna = mock_vna()
        gate = mock_parameter("gate", unit="V", label="Gate")
        s = Sweep1D(gate, 0, 1, 0.1, **fast_sweep_kwargs)
        s.follow_param(vna.s21_magnitude, vna.s21_phase)
        assert len(s._params) == 2
        assert vna.s21_magnitude in s._params
        assert vna.s21_phase in s._params
