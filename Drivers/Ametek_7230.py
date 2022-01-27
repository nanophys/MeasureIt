from typing import ClassVar, Dict
import time

from qcodes import VisaInstrument
from qcodes.utils.validators import Strings, Enum


class Ametek_7230(VisaInstrument):
    """
    Class for Ametek 7230 lock-in amplifier.
    """
    SENSITIVITY: ClassVar[Dict[str, int]] = {
        '10 nV': 3,
        '20 nV': 4,
        '50 nV': 5,
        '100 nV': 6,
        '200 nV': 7,
        '500 nV': 8,
        '1 uV': 9,
        '2 uV': 10,
        '5 uV': 11,
        '10 uV': 12,
        '20 uV': 13,
        '50 uV': 14,
        '100 uV': 15,
        '200 uV': 16,
        '500 uV': 17,
        '1 mV': 18,
        '2 mV': 19,
        '5 mV': 20,
        '10 mV': 21,
        '20 mV': 22,
        '50 mV': 23,
        '100 mV': 24,
        '200 mV': 25,
        '500 mV': 26,
        '1 V': 27
    }
    TIME_CONSTANT: ClassVar[Dict[str, int]] = {
        '10 us': 0,
        '20 us': 1,
        '50 us': 2,
        '100 us': 3,
        '200 us': 4,
        '500 us': 5,
        '1 ms': 6,
        '2 ms': 7,
        '5 ms': 8,
        '10 ms': 9,
        '20 ms': 10,
        '50 ms': 11,
        '100 ms': 12,
        '200 ms': 13,
        '500 ms': 14,
        '1 s': 15,
        '2 s': 16,
        '5 s': 17,
        '10 s': 18,
        '20 s': 19,
        '50 s': 20,
        '100 s': 21,
        '200 s': 22,
        '500 s': 23,
        '1 ks': 24,
        '2 ks': 25,
        '5 ks': 26,
        '10 ks': 27,
        '20 ks': 28,
        '50 ks': 29,
        '100 ks': 30
    }
    AC_GAIN: ClassVar[Dict[str, int]] = {
        '0 dB': 0,
        '6 dB': 1,
        '12 dB': 2,
        '18 dB': 3,
        '24 dB': 4,
        '30 dB': 5,
        '36 dB': 6,
        '42 dB': 7,
        '48 dB': 8,
        '54 dB': 9,
        '60 dB': 10,
        '66 dB': 11,
        '72 dB': 12,
        '78 dB': 13,
        '84 dB': 14,
        '90 dB': 15
    }
    REFERENCE_SOURCE: ClassVar[Dict[str, int]] = {
        'INT': 0,
        'EXT TTL': 1,
        'EXT ANALOG': 2
    }

    def __init__(self, name: str, address: str, terminator='\n\x00', *args, **kwargs):
        VisaInstrument.__init__(self, name, address, terminator=terminator, **kwargs)

        self.add_parameter('X',
                           label='X',
                           docstring='X component of input signal',
                           get_parser=float,
                           get_cmd='X.')

        self.add_parameter('Y',
                           label='Y',
                           docstring='Y component of input signal',
                           get_parser=float,
                           get_cmd='Y.')

        self.add_parameter('P',
                           label='Phase',
                           docstring='Phase of input signal',
                           get_parser=float,
                           get_cmd='PHA.')

        self.add_parameter('R',
                           label='R',
                           docstring='Magnitude of input signal',
                           get_parser=float,
                           get_cmd='MAG.')

        self.add_parameter('time_constant',
                           label='time constant',
                           docstring='Output filter time constant',
                           get_cmd='TC',
                           set_cmd='TC {}',
                           val_mapping=self.TIME_CONSTANT)

        self.add_parameter('reference',
                           label='reference',
                           docstring='Reference channel source control',
                           get_cmd='IE',
                           set_cmd='IE {}',
                           val_mapping=self.REFERENCE_SOURCE)

        self.add_parameter('frequency',
                           label='frequency',
                           docstring='Reference frequency for the lock-in amplifier',
                           get_cmd='FRQ.')

        self.add_parameter('sensitivity',
                           label='sensitivity',
                           docstring='Full-scale sensitivity',
                           get_cmd='SEN',
                           set_cmd='SEN {}',
                           val_mapping=self.SENSITIVITY)

        con_msg = f"Connected to: Ametek {self.ask('ID')} (firmware:{self.ask('VER')}) in {time.time() - self._t0}"
        print(con_msg)
        self.log.info(f"Connected to instrument: {}")
