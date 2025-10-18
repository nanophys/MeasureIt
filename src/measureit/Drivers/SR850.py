from typing import Optional

from qcodes.instrument.visa import VisaInstrument
from qcodes.validators import Numbers


class SR850(VisaInstrument):
    """Minimal QCoDeS driver for the Stanford Research Systems SR850 Lock-in Amplifier.
    Provides basic functionality.
    """

    def __init__(self, name: str, address: str, **kwargs):
        """Initializes the SR850 driver.

        Args:
            name (str): Local name for the instrument.
            address (str): VISA resource string, e.g., 'GPIB0::8::INSTR'.
            **kwargs: Additional keyword arguments forwarded to VisaInstrument.
        """
        super().__init__(name, address, **kwargs)

        self.X: Parameter = self.add_parameter(
            "X",
            get_cmd="OUTP? 1",
            get_parser=float,
            label="X Channel",
            unit="V",
        )

        self.Y: Parameter = self.add_parameter(
            "Y",
            get_cmd="OUTP? 2",
            get_parser=float,
            label="Y Channel",
            unit="V",
        )

        self.R: Parameter = self.add_parameter(
            "R",
            get_cmd="OUTP? 3",
            get_parser=float,
            label="R Channel",
            unit="V",
        )

        self.P: Parameter = self.add_parameter(
            "P",
            get_cmd="OUTP? 4",
            get_parser=float,
            label="Phase Channel",
            unit="deg",
        )

        self.frequency: Parameter = self.add_parameter(
            "frequency",
            label="Frequency",
            get_cmd="FREQ?",
            get_parser=float,
            set_cmd="FREQ{:.4f}",
            unit="Hz",
            vals=Numbers(min_value=1e-3, max_value=102e3),
        )

        self.time_constant: Parameter = self.add_parameter(
            "time_constant",
            label="Time constant",
            get_cmd="OFLT?",
            set_cmd="OFLT {}",
            unit="s",
            val_mapping={
                10e-6: 0,
                30e-6: 1,
                100e-6: 2,
                300e-6: 3,
                1e-3: 4,
                3e-3: 5,
                10e-3: 6,
                30e-3: 7,
                100e-3: 8,
                300e-3: 9,
                1: 10,
                3: 11,
                10: 12,
                30: 13,
                100: 14,
                300: 15,
                1e3: 16,
                3e3: 17,
                10e3: 18,
                30e3: 19,
            },
        )

        self.filter_slope: Parameter = self.add_parameter(
            "filter_slope",
            label="Filter slope",
            get_cmd="OFSL?",
            set_cmd="OFSL {}",
            unit="dB/oct",
            val_mapping={
                6: 0,
                12: 1,
                18: 2,
                24: 3,
            },
        )

        self.amplitude: Parameter = self.add_parameter(
            "amplitude",
            label="Amplitude",
            get_cmd="SLVL?",
            get_parser=float,
            set_cmd="SLVL {:.3f}",
            unit="V",
            vals=Numbers(min_value=0.004, max_value=5.000),
        )

        self.add_function("auto_phase", call_cmd="APHS")

        for i in [1, 2, 3, 4]:
            self.add_parameter(
                f"aux_in{i}",
                label=f"Aux input {i}",
                get_cmd=f"OAUX? {i}",
                get_parser=float,
                unit="V",
            )

            self.add_parameter(
                f"aux_out{i}",
                label=f"Aux output {i}",
                get_cmd=f"AUXV? {i}",
                get_parser=float,
                set_cmd=f"AUXV {i}, {{}}",
                unit="V",
            )

        self.connect_message()

    def get_idn(self) -> dict[str, Optional[str]]:
        vendor = "Stanford Research Systems"
        model = "SR850"
        serial = None
        firmware = None

        return {
            "vendor": vendor,
            "model": model,
            "serial": serial,
            "firmware": firmware,
        }
