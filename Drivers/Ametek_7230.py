from typing import ClassVar, Dict
import time

from qcodes import VisaInstrument
from qcodes.utils.validators import Strings, Enum
from qcodes.utils.delaykeyboardinterrupt import DelayedKeyboardInterrupt


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

    def __init__(self, name: str, address: str, terminator='\r', *args, **kwargs):
        VisaInstrument.__init__(self, name, address, terminator=terminator, **kwargs)

        self.add_parameter('X',
                           label='X',
                           docstring='X component of input signal',
                           get_parser=float,
                           get_cmd='X.',
                           unit='V')

        self.add_parameter('Y',
                           label='Y',
                           docstring='Y component of input signal',
                           get_parser=float,
                           get_cmd='Y.',
                           unit='V')

        self.add_parameter('P',
                           label='Phase',
                           docstring='Phase of input signal',
                           get_parser=float,
                           get_cmd='PHA.',
                           unit='deg')

        self.add_parameter('R',
                           label='R',
                           docstring='Magnitude of input signal',
                           get_parser=float,
                           get_cmd='MAG.',
                           unit='V')

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
                           val_mapping={
                               'INT': 0,
                               'EXT TTL': 1,
                               'EXT ANALOG': 2
                           })

        self.add_parameter('frequency',
                           label='frequency',
                           docstring='Reference frequency for the lock-in amplifier',
                           get_cmd='FRQ.',
                           unit='Hz')

        self.add_parameter('sensitivity',
                           label='sensitivity',
                           docstring='Full-scale sensitivity',
                           get_cmd='SEN',
                           set_cmd='SEN {}',
                           val_mapping=self.SENSITIVITY)

        self.add_parameter('ac_gain',
                           label='ac gain',
                           get_cmd='ACGAIN',
                           set_cmd='ACGAIN {}',
                           val_mapping=self.AC_GAIN)

        self.add_parameter('i_mode',
                           label='i_mode',
                           docstring='Current/voltage mode input selector',
                           get_cmd='IMODE',
                           set_cmd='IMODE {}',
                           val_mapping={
                               'Off': 0,
                               'High bandwidth': 1,
                               'Low noise': 2
                           })

        self.add_parameter('v_mode',
                           label='v_mode',
                           docstring='Voltage input configuration',
                           get_cmd='VMODE',
                           set_cmd='VMODE {}',
                           val_mapping={
                               'Grounded': 0,
                               'A': 1,
                               'B': 2,
                               'A-B': 3
                           })

        self.add_parameter('coupling',
                           label='coupling',
                           get_cmd='FET',
                           set_cmd='FET {}',
                           val_mapping={
                               'AC': 0,
                               'DC': 1
                           })

        self.add_parameter('shield',
                           label='shield',
                           get_cmd='FLOAT',
                           set_cmd='FLOAT {}',
                           val_mapping={
                               'ground': 0,
                               'float': 1
                           })

        self.add_parameter('FET',
                           label='FET',
                           get_cmd='FET',
                           set_cmd='FET {}',
                           val_mapping={
                               'bipolar': 0,
                               'FET': 1
                           })

        self.add_function('autosensitivity', call_cmd='AS')

        self.connect_message()

    def get_idn(self):
        """
        Support for generic VISA '*IDN?' query.

        Returns:
            A dict containing vendor, model, serial, and firmware.
        """
        vendor = 'Ametek'
        model = self.ask('ID')
        serial = self.ask('NAME').strip()
        firmware = self.ask('VER')

        return dict(zip(('vendor', 'model', 'serial', 'firmware'), [vendor, model, serial, firmware]))

    def write_raw(self, cmd: str):
        """
        Low-level interface to ``visa_handle.ask``.

        Args:
            cmd: The command to send to the instrument.

        We overwrite the default implementation of ``write_raw`` because the instrument sends back an empty response
        after a write, so we need to grab that to prevent a backlog in the buffer.
        """
        with DelayedKeyboardInterrupt():
            self.visa_log.debug(f"Writing: {cmd}")
            self.visa_handle.query(cmd)
