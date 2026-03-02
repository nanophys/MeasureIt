"""Mock instruments for testing MeasureIt without hardware dependencies."""

from typing import Dict, Optional

import numpy as np
from qcodes import Instrument
from qcodes.parameters import Parameter, ParameterWithSetpoints
from qcodes.validators import Arrays


class MockParameter(Parameter):
    """A simple mock parameter that stores values in memory."""

    def __init__(self, name: str, initial_value: float = 0.0, **kwargs):
        """Initialize mock parameter.

        Args:
            name: Parameter name
            initial_value: Initial value
            **kwargs: Additional parameter kwargs (unit, label, etc.)
        """
        super().__init__(name=name, **kwargs)
        self._value = initial_value

    def get_raw(self) -> float:
        """Get current value."""
        return self._value

    def set_raw(self, value: float) -> None:
        """Set new value."""
        self._value = value


class MockLockIn(Instrument):
    """Mock lock-in amplifier (e.g., SR830)."""

    def __init__(self, name: str, **kwargs):
        """Initialize mock lock-in.

        Args:
            name: Instrument name
            **kwargs: Additional instrument kwargs
        """
        super().__init__(name, **kwargs)

        self.add_parameter(
            "x",
            parameter_class=MockParameter,
            initial_value=0.0,
            unit="V",
            label="X",
        )

        self.add_parameter(
            "y",
            parameter_class=MockParameter,
            initial_value=0.0,
            unit="V",
            label="Y",
        )

        self.add_parameter(
            "phase",
            parameter_class=MockParameter,
            initial_value=0.0,
            unit="deg",
            label="Phase",
        )

        self.add_parameter(
            "frequency",
            parameter_class=MockParameter,
            initial_value=1000.0,
            unit="Hz",
            label="Frequency",
        )


class MockVoltageSource(Instrument):
    """Mock voltage source (e.g., Keithley)."""

    def __init__(self, name: str, **kwargs):
        """Initialize mock voltage source.

        Args:
            name: Instrument name
            **kwargs: Additional instrument kwargs
        """
        super().__init__(name, **kwargs)

        self.add_parameter(
            "voltage",
            parameter_class=MockParameter,
            initial_value=0.0,
            unit="V",
            label="Voltage",
        )

        self.add_parameter(
            "current",
            parameter_class=MockParameter,
            initial_value=0.0,
            unit="A",
            label="Current",
        )

        self.add_parameter(
            "output",
            parameter_class=MockParameter,
            initial_value=0.0,
            unit="",
            label="Output State",
        )


class MockTemperatureController(Instrument):
    """Mock temperature controller (e.g., Lakeshore)."""

    def __init__(self, name: str, **kwargs):
        """Initialize mock temperature controller.

        Args:
            name: Instrument name
            **kwargs: Additional instrument kwargs
        """
        super().__init__(name, **kwargs)

        self.add_parameter(
            "temperature",
            parameter_class=MockParameter,
            initial_value=300.0,
            unit="K",
            label="Temperature",
        )

        self.add_parameter(
            "setpoint",
            parameter_class=MockParameter,
            initial_value=300.0,
            unit="K",
            label="Setpoint",
        )


class FailingParameter(Parameter):
    """A parameter that fails to set above a threshold value."""

    def __init__(self, name: str, fail_above: float = 7.8, initial_value: float = 0.0, **kwargs):
        """Initialize failing parameter.

        Args:
            name: Parameter name
            fail_above: Threshold above which set() will fail
            initial_value: Initial value
            **kwargs: Additional parameter kwargs (unit, label, etc.)
        """
        super().__init__(name=name, **kwargs)
        self._value = initial_value
        self._fail_above = fail_above

    def get_raw(self) -> float:
        """Get current value."""
        return self._value

    def set_raw(self, value: float) -> None:
        """Set new value, fails if value exceeds threshold."""
        if value > self._fail_above:
            raise ValueError(f"Couldn't set {self.name} to {value}.")
        self._value = value


class MockMagnet(Instrument):
    """Mock magnet power supply that fails above a threshold."""

    def __init__(self, name: str, fail_above: float = 7.8, **kwargs):
        """Initialize mock magnet.

        Args:
            name: Instrument name
            fail_above: B field threshold above which set() will fail
            **kwargs: Additional instrument kwargs
        """
        super().__init__(name, **kwargs)

        self.add_parameter(
            "B",
            parameter_class=FailingParameter,
            fail_above=fail_above,
            initial_value=0.0,
            unit="T",
            label="Magnetic field",
        )


class MockGate(Instrument):
    """Mock gate voltage source."""

    def __init__(self, name: str, **kwargs):
        """Initialize mock gate.

        Args:
            name: Instrument name
            **kwargs: Additional instrument kwargs
        """
        super().__init__(name, **kwargs)

        self.add_parameter(
            "Vtg",
            parameter_class=MockParameter,
            initial_value=0.0,
            unit="V",
            label="Top-gate voltage",
        )


class _PixelsParameter(Parameter):
    """Setpoints parameter returning pixel indices for MockSpectrometer."""

    def __init__(self, name: str, instrument: Instrument, n_pixels_param: str, **kwargs):
        super().__init__(name=name, instrument=instrument, **kwargs)
        self._n_pixels_param = n_pixels_param

    def get_raw(self):
        n = self.instrument.parameters[self._n_pixels_param].get()
        return np.arange(int(n), dtype=np.float64)


class _SpectrumParameter(ParameterWithSetpoints):
    """Spectrum data parameter for MockSpectrometer."""

    def __init__(self, name: str, instrument: Instrument, **kwargs):
        super().__init__(name=name, instrument=instrument, **kwargs)

    def get_raw(self):
        n = int(self.instrument.n_pixels.get())
        center = self.instrument._center
        width = self.instrument._width
        noise_amp = self.instrument._noise_amp
        pixels = np.arange(n, dtype=np.float64)
        gaussian = np.exp(-0.5 * ((pixels - center) / width) ** 2)
        return gaussian + noise_amp * np.random.default_rng().uniform(-1, 1, n)


class MockSpectrometer(Instrument):
    """Mock spectrometer that returns array-valued spectrum data."""

    def __init__(
        self,
        name: str,
        n_pixels: int = 128,
        center: float = 64.0,
        width: float = 10.0,
        noise_amp: float = 0.01,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self._center = center
        self._width = width
        self._noise_amp = noise_amp

        self.add_parameter(
            "n_pixels",
            parameter_class=MockParameter,
            initial_value=float(n_pixels),
            unit="",
            label="Number of pixels",
        )

        self.add_parameter(
            "pixels",
            parameter_class=_PixelsParameter,
            n_pixels_param="n_pixels",
            unit="px",
            label="Pixel",
            vals=Arrays(shape=(n_pixels,)),
        )

        self.add_parameter(
            "spectrum",
            parameter_class=_SpectrumParameter,
            unit="counts",
            label="Spectrum",
            vals=Arrays(shape=(n_pixels,)),
            setpoints=(self.pixels,),
        )


class _FrequencyParameter(Parameter):
    """Setpoints parameter returning frequency array for MockVNA."""

    def __init__(
        self,
        name: str,
        instrument: Instrument,
        n_points_param: str,
        **kwargs,
    ):
        super().__init__(name=name, instrument=instrument, **kwargs)
        self._n_points_param = n_points_param

    def get_raw(self):
        n = int(self.instrument.parameters[self._n_points_param].get())
        return np.linspace(
            self.instrument._f_start,
            self.instrument._f_stop,
            n,
            dtype=np.float64,
        )


class _S21MagnitudeParameter(ParameterWithSetpoints):
    """S21 magnitude parameter for MockVNA."""

    def __init__(self, name: str, instrument: Instrument, **kwargs):
        super().__init__(name=name, instrument=instrument, **kwargs)

    def get_raw(self):
        n = int(self.instrument.n_points.get())
        freqs = np.linspace(self.instrument._f_start, self.instrument._f_stop, n)
        f0 = self.instrument._resonance_freq
        Q = self.instrument._q_factor
        lorentzian = 1.0 / (1.0 + Q**2 * ((freqs - f0) / f0) ** 2)
        return -20.0 * lorentzian  # dB dip


class _S21PhaseParameter(ParameterWithSetpoints):
    """S21 phase parameter for MockVNA."""

    def __init__(self, name: str, instrument: Instrument, **kwargs):
        super().__init__(name=name, instrument=instrument, **kwargs)

    def get_raw(self):
        n = int(self.instrument.n_points.get())
        freqs = np.linspace(self.instrument._f_start, self.instrument._f_stop, n)
        f0 = self.instrument._resonance_freq
        Q = self.instrument._q_factor
        return np.degrees(np.arctan2(-Q * (freqs - f0) / f0, 1.0))


class MockVNA(Instrument):
    """Mock Vector Network Analyzer returning array-valued S-parameters."""

    def __init__(
        self,
        name: str,
        n_points: int = 201,
        f_start: float = 4e9,
        f_stop: float = 8e9,
        resonance_freq: float = 6e9,
        q_factor: float = 1000.0,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self._f_start = f_start
        self._f_stop = f_stop
        self._resonance_freq = resonance_freq
        self._q_factor = q_factor

        self.add_parameter(
            "n_points",
            parameter_class=MockParameter,
            initial_value=float(n_points),
            unit="",
            label="Number of points",
        )

        self.add_parameter(
            "frequency",
            parameter_class=_FrequencyParameter,
            n_points_param="n_points",
            unit="Hz",
            label="Frequency",
            vals=Arrays(shape=(n_points,)),
        )

        self.add_parameter(
            "s21_magnitude",
            parameter_class=_S21MagnitudeParameter,
            unit="dB",
            label="S21 Magnitude",
            vals=Arrays(shape=(n_points,)),
            setpoints=(self.frequency,),
        )

        self.add_parameter(
            "s21_phase",
            parameter_class=_S21PhaseParameter,
            unit="deg",
            label="S21 Phase",
            vals=Arrays(shape=(n_points,)),
            setpoints=(self.frequency,),
        )

        self.add_parameter(
            "power",
            parameter_class=MockParameter,
            initial_value=-20.0,
            unit="dBm",
            label="Drive power",
        )


def create_mock_station():
    """Create a Station with common mock instruments.

    Returns:
        Station with mock instruments attached
    """
    from qcodes import Station

    station = Station()

    # Add mock instruments
    sr830 = MockLockIn("SR830")
    keithley = MockVoltageSource("Keithley")
    lakeshore = MockTemperatureController("Lakeshore")

    station.add_component(sr830)
    station.add_component(keithley)
    station.add_component(lakeshore)

    return station
