import qcodes as qc
import logging
from qcodes import VisaInstrument
import qcodes.utils.validators as vals
from typing import Dict, List, Optional, Sequence, Any, Union
import numpy as np
import logging
from time import sleep

log = logging.getLogger(__name__)
MIN_FIELD = -50 #kG
MAX_FIELD = 50 #kG
class Attodrymagnet_z(VisaInstrument):
    def __init__(self, name: str, address, **kwargs):
        super().__init__(name, address, terminator='\n',**kwargs)
        self.add_parameter('field',
                           get_cmd=self._get_field,
                           get_parser=float,
                           set_cmd=self._set_field,
                           unit='T',
                           label='Magnetic Field',
                           vals=vals.Numbers(MIN_FIELD, MAX_FIELD))
        self.add_parameter('rate',
                           get_cmd=self._get_rate,
                           set_cmd=self._set_rate,
                           get_parser=float,
                           )
        self.write('REMOTE')
        self.write('CHAN 1') #z magnet
        self.write('UNITS T')
        self.write('CHAN 2') #z magnet
        self.write('UNITS T')
        self.idn = self.ask('*idn?')
        self.units = 'T'
        self.write('CHAN 1') #z magnet
        print('Connent to:'+self.idn)

    def _get_field(self):
        self.change_state()
        result = self.ask('IMAG?')
        
        for i in range(10): #Sometimes the magnet returns the IMAG? query for some reason. If this happens, wait one second and try asking again
            try: 
                float(result[:-2])
                break
            except:
                print('Communication error: returned value ' + result)
                sleep(1.0)
                self.change_state()
                result = self.ask('IMAG?')
        return (float(result[:-2]))/10.0
    def _set_field(self,val):
        cur = self._get_field()
        if val>cur:
            self.change_state()
            self.setpoint(cur*10.0,val*10.0)
            self.write('SWEEP UP')
        else:
            self.change_state()
            self.setpoint(val*10.0,cur*10.0)
            self.write('SWEEP DOWN')
    def _get_rate(self):
        self.change_state()
        result = self.ask('RATE?')
        return float(result)/10
    def _set_rate(self, val):
        rate = val*10 #kG/s
        self.change_state()
        self.write('RATE 0 {}'.format(rate))
        self.write('RATE 1 {}'.format(rate))
    def setpoint(self, llim, ulim):
        llim_setpoint = llim
        ulim_setpoint = ulim
        self.change_state()
        self.write('LLIM {}'.format(llim_setpoint))
        self.write('ULIM {}'.format(ulim_setpoint))
    def change_state(self):
        self.write('CHAN 1')
    

