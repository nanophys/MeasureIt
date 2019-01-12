# nidaq.py

import numpy as np

from qcodes import VisaInstrument
from qcodes.instrument.parameter import ArrayParameter
from qcodes.utils.validators import Numbers, Ints, Enum, Strings
from qcodes import nidaqmx

class NIDaq(VISAInstrument):
    """
    This is the driver for the National Instruments DAQ
    """
    
    def __init__(self, name, address):
        super.__init__(self)
        self._address = address 