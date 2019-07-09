# util.py
# Utility function file

import re
import time
import qcodes as qc
from qcodes.instrument_drivers.stanford_research.SR860 import SR860

unit_dict = [
        {'f', 10**-15},
        {'p', 10**-12},
        {'n', 10**-9},
        {'u', 10**-6},
        {'m', 10**-3},
        {'k', 10**3},
        {'M', 10**6},
        {'G', 10**9}
        ]

def set_experiment_sample_names(sweep, exp, samp):
    if sweep.save_data is True:
        qc.new_experiment(exp, samp)
    sweep._create_measurement()
    
def _value_parser(value):
    """
    Parses user input for a float and a unit prefix character. Returns a float
    and a single char
    """
    value = str(value).strip()
    
    if value[0] == '.':
        value = '0' + value
    # regex testing stripped value as valid factor string
    # must be exactly a number followed by (space optional) single valid factor char 
    # f = femto p = pico u = micro m = milli k = kilo M = Mega G = Giga
    regex = re.compile(r"^([-]?[\d]*.?[\d]+[\s]?)([fpnumkMG]?)$")
    
    parsedVal = regex.search(value)
    if not parsedVal:
        return -1
    
    return (float(parsedVal.groups(' ')[0]), parsedVal.groups(' ')[1])
    
def _autorange_srs(srs, max_changes=1):
    """
    Joe's code, unedited
    """
    def autorange_once():
        r = srs.R.get()
        sens = srs.sensitivity.get()
        if r > 0.9 * sens:
            return srs.increment_sensitivity()
        elif r < 0.1 * sens:
            return srs.decrement_sensitivity()
        return False
    sets = 0
    while autorange_once() and sets < max_changes:
        sets += 1
        time.sleep(10*srs.time_constant.get())