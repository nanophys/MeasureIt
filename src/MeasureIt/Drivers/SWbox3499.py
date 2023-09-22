from time import sleep, time
import numpy as np
import ctypes  # only for DLL-based instrument

import qcodes as qc
from qcodes import (Instrument, VisaInstrument,
                    ManualParameter, MultiParameter,
                    validators as vals)
from qcodes.instrument.channel import InstrumentChannel
class swbox(VisaInstrument):
    """
    QCoDeS driver for the stepped attenuator
    Weinschel is formerly known as Aeroflex/Weinschel
    """

    # all instrument constructors should accept **kwargs and pass them on to
    # super().__init__
    def __init__(self, name, address, **kwargs):
        # supplying the terminator means you don't need to remove it from every response
        super().__init__(name, address, **kwargs)

        #self.add_parameter('getStat',
                           # the value you set will be inserted in this command with
                           # regular python string substitution. This instrument wants
                           # an integer zero-padded to 2 digits. For robustness, don't
                           # assume you'll get an integer input though - try to allow
                           # floats (as opposed to {:0=2d})
                           
                           # set_cmd=self._close_ch,
                           # setting any attenuation other than 0, 2, ... 60 will error.
                           #vals=vals.Enum(*np.arange(0, 60.1, 2).tolist()),
                           # the return value of get() is a string, but we want to
                           # turn it into a (float) number
                           #)

        # it's a good idea to call connect_message at the end of your constructor.
        # this calls the 'IDN' parameter that the base Instrument class creates for
        # every instrument (you can override the `get_idn` method if it doesn't work
        # in the standard VISA form for your instrument) which serves two purposes:
        # 1) verifies that you are connected to the instrument
        # 2) gets the ID info so it will be included with metadata snapshots later.
        self.connect_message()
    # def _close_ch(self):
        #self.write('ROUT:CLOS:STAT?')
        #st = self.ask_raw()
        #while st =='\n':
        #    self.write_raw('GET 0')
        #    st = self.ask_raw('')
        #return st
    def get_stat(self):
        self.write_raw('ROUT:CLOS:STAT?')
        st = self.ask_raw('')
        return st
    
    def close_ch(self,ch: str):
        self.write_raw('ROUT:CLOS (@%s)' % ch)
        print(self.get_stat())
        return
    
    def open_ch(self,ch: str):
        if ch == 'all':
            self.write_raw('ROUT:OPEN ALL')
        else:
            self.write_raw('ROUT:OPEN (@%s)' % ch)
            
        print(self.get_stat())
        return
        
    
    
# instantiating and using this instrument (commented out because I can't actually do it!)
#
# from qcodes.instrument_drivers.weinschel.Weinschel_8320 import Weinschel_8320
# weinschel = Weinschel_8320('w8320_1', 'TCPIP0::172.20.2.212::inst0::INSTR')
# weinschel.attenuation(40)