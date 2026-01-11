"""Mock instruments for testing MeasureIt without hardware dependencies."""

from typing import Dict, Optional

from qcodes import Instrument
from qcodes.parameters import Parameter


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
