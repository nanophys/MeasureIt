# nidaq.py

import numpy as np

from qcodes import VisaInstrument
from qcodes.instrument.parameter import ArrayParameter
from qcodes.utils.validators import Numbers, Ints, Enum, Strings
import nidaqmx

class NIDaq():
    """
    This is the driver for the National Instruments DAQ
    """
    
    def __init__(self, name, address, ao_num, ai_num):
        self._name = name
        self._address = address
        system = nidaqmx.system.System.local()
        self.device = system.devices[address]
        self.ao_chan = nidaqmx.Task()
        self.ai_chan = nidaqmx.Task()
        
        for ao in range(ao_num):
            ao_name = self._address + "/ao" + str(ao)
            self.ao_chan.ao_channels.add_ao_voltage_chan(ao_name)
        for ai in range(ai_num):
            ai_name = self._address + "/ai" + str(ai)
            self.ai_chan.ai_channels.add_ai_voltage_chan(ai_name)
            
        
    def test_init(self):
        print(self.ao_chan.channel_names)
        print(self.ai_chan.channel_names)




        
test = NIDaq("testdaq", "Dev1", 2, 24)
test.test_init()