from typing import ClassVar, Dict

import pyvisa as visa
from pyvisa.resources.serial import SerialInstrument

from qcodes.instrument import VisaInstrument
from qcodes.instrument.group_parameter import GroupParameter, Group


class VGC503(VisaInstrument):
    PRESSURE_UNIT: ClassVar[Dict[str, str]] = {
        'bar': '0',
        'Torr': '1',
        'Pa': '2',
        'Micron': '3',
        'hPascal': '4',
        'Volt': '5'}

    STATUS: ClassVar[Dict[str, str]] = {
        'Measurement data okay': '0',
        'Underrange': '1',
        'Overrange': '2',
        'Sensor error': '3',
        'Sensor off': '4',
        'No sensor': '5',
        'Identification error': '6',
        'Error BPG, HPG, BCG': '7'
    }

    def __init__(self, name, address, baud_rate=115200, *args, **kwargs):
        super().__init__(name, address, terminator='', *args, **kwargs)
        handle = self.visa_handle
        assert isinstance(handle, SerialInstrument)
        handle.baud_rate = baud_rate
        handle.parity = visa.constants.Parity(0)
        handle.data_bits = 8

        self.add_parameter('P1',
                           label='Pressure 1',
                           get_parser=float,
                           parameter_class=GroupParameter
                           )

        self.add_parameter('S1',
                           label='Status of gauge 1',
                           parameter_class=GroupParameter,
                           val_mapping=self.STATUS
                           )

        self.add_parameter('P2',
                           label='Pressure 2',
                           get_parser=float,
                           parameter_class=GroupParameter
                           )

        self.add_parameter('S2',
                           label='Status of gauge 2',
                           parameter_class=GroupParameter,
                           val_mapping=self.STATUS
                           )

        self.add_parameter('P3',
                           label='Pressure 3',
                           get_parser=float,
                           parameter_class=GroupParameter
                           )

        self.add_parameter('S3',
                           label='Status of gauge 3',
                           parameter_class=GroupParameter,
                           val_mapping=self.STATUS
                           )

        self.pressure_group = Group([self.S1, self.P1, self.S2, self.P2, self.S3, self.P3],
                                    get_cmd=f'PRX')

        self.add_parameter('unit',
                           label='unit',
                           get_cmd='UNI',
                           set_cmd='UNI,{}',
                           val_mapping=self.PRESSURE_UNIT)

        self.add_parameter('sensors',
                           label='sensors',
                           get_cmd='TID')

        self.connect_message()

    def get_idn(self):
        msg = self.ask_raw('AYT')

        [product, model, serial, firmware, hardware] = msg.split(',')
        vendor = 'Inficon'

        return dict(zip(('vendor', 'model', 'serial', 'firmware'), [vendor, f'{product} {model}', serial, firmware]))

    def ask_raw(self, msg):
        check = super().ask_raw(msg + '\r\n')
        if '\x06' in check:
            ans = super().ask_raw('\x05')
        elif '\x15' in check:
            raise Exception(f'Negative acknowledge received while sending message: {msg}')
        else:
            raise Exception(f'Unknown error while sending message: {msg}')

        ans = ans.replace('\r\n', '')
        return ans

    def write_raw(self, msg):
        self.ask_raw(msg)
