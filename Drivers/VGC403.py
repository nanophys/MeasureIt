from typing import ClassVar, Dict

import pyvisa as visa
from pyvisa.resources.serial import SerialInstrument

from qcodes.instrument import VisaInstrument

class VGC403(VisaInstrument):
    
    PRESSURE_UNIT: ClassVar[Dict[str, str]] = {
        'bar': '1',
        'Torr': '2',
        'Pa': '3',
        'Micron': '4'}
    
    def __init__(self, name, address, baud_rate=38400, *args, **kwargs):
        
        super().__init__(name, address, **kwargs)
        handle = self.visa_handle
        assert isinstance(handle, SerialInstrument)
        handle.baud_rate = baud_rate
        handle.parity = visa.constants.Parity(0)
        handle.data_bits = 8
        self.set_terminator('\r\n')
        handle.write_termination = '\r\n'
        
        self.add_parameter('P1',
                           label='P1',
                           get_cmd='PR1',
                          )
        
        self.add_parameter('P2',
                           label='P2',
                           get_cmd='PR2',
                          )
        
        self.add_parameter('P3',
                           label='P3',
                           get_cmd='PR3',
                          )
        
        self.add_parameter('unit',
                           label='unit',
                           get_cmd='UNI',
                           set_cmd='UNI,{}',
                           val_mapping=self.PRESSURE_UNIT)
        
        self.add_parameter('sensors',
                           label='sensors',
                           get_cmd='TID')
        
    def ask_raw(self, msg):
        check = super().ask_raw(msg)
        if '\x06' in check:
            ans = super().ask_raw('\x05')
        elif '\x15' in check:
            raise Exception(f'Unknown command: {msg}')
            
        return ans
    
    def write_raw(self, msg):
        self.ask_raw(msg)
        